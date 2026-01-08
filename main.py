"""
ARCore + Open3D 3D再構成サーバー

COLMAPを使用せず、ARCoreのVIOポーズを直接利用した高速3D再構成
"""

import os
import sys
import json
import uuid
import shutil
import yaml
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
import open3d as o3d

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import aiofiles

# 最大アップロードサイズ: 1GB
MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1GB in bytes

# パイプライン
from utils.arcore_parser import ARCoreDataParser
# GPU対応版を優先的に使用
try:
    from pipeline.rgbd_integration_gpu import RGBDIntegrationGPU as RGBDIntegration
    from pipeline.mesh_generation_gpu import MeshGeneratorGPU as MeshGenerator, create_mesh_from_rgbd_volume_gpu as create_mesh_from_rgbd_volume
    GPU_AVAILABLE = True
    print("✓ Using GPU-accelerated pipeline")
except ImportError:
    # フォールバック: CPU版を使用
    from pipeline.rgbd_integration import RGBDIntegration
    from pipeline.mesh_generation import MeshGenerator, create_mesh_from_rgbd_volume
    GPU_AVAILABLE = False
    print("⚠ GPU pipeline not available, using CPU pipeline")

from pipeline.rgbd_integration import PointCloudFusion

# ============================================================
# 設定読み込み
# ============================================================

CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {}

CONFIG = load_config()

# ============================================================
# アプリケーション設定
# ============================================================

app = FastAPI(
    title="ARCore + Open3D 3D Reconstruction Server",
    description="High-speed 3D reconstruction using ARCore poses and Open3D",
    version="1.0.0"
)

# 大容量アップロード用のリミット設定
# Starlette/FastAPIのmultipartパーサーを直接パッチ
import starlette.formparsers

_original_init = starlette.formparsers.MultiPartParser.__init__

def _patched_init(self, headers, stream, *, max_files=10000, max_fields=10000, max_part_size=1024*1024*1024):
    """大容量アップロード対応: max_files=10000, max_part_size=1GB"""
    _original_init(self, headers, stream, max_files=max_files, max_fields=max_fields, max_part_size=max_part_size)

starlette.formparsers.MultiPartParser.__init__ = _patched_init
print(f"✓ Upload limits: max_files=10000, max_part_size=1GB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# グローバル例外ハンドラー（フォームパース時のエラーをキャッチ）
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"Validation Error: {exc}")
    print(f"  Body: {exc.body if hasattr(exc, 'body') else 'N/A'}")
    for error in exc.errors():
        print(f"  - {error}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc.errors())}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Global Exception: {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {type(exc).__name__}"}
    )


# リクエストのロギング（デバッグ用）
@app.middleware("http")
async def log_requests(request, call_next):
    """リクエストとレスポンスをログに記録"""
    import time
    start_time = time.time()
    
    # リクエスト情報をログ
    print(f"Request: {request.method} {request.url.path}")
    if request.method == "POST" and "/api/v1/sessions/upload" in str(request.url.path):
        # ファイルアップロードリクエストの場合、詳細をログ
        print(f"  Content-Type: {request.headers.get('content-type', 'N/A')}")
        print(f"  Content-Length: {request.headers.get('content-length', 'N/A')}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"Response: {response.status_code} (took {process_time:.3f}s)")
        # 400エラーの場合、詳細をログ
        if response.status_code == 400:
            print(f"  WARNING: 400 Bad Request returned")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"Error: {type(e).__name__}: {e} (took {process_time:.3f}s)")
        import traceback
        traceback.print_exc()
        raise

# ディレクトリ設定
server_config = CONFIG.get('server', {})
DATA_DIR = Path(server_config.get('data_dir', '/opt/arcore-3dmapper-open3d/data'))
SESSIONS_DIR = DATA_DIR / "sessions"
RESULTS_DIR = DATA_DIR / "results"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 静的ファイル配信
# 結果ファイル用のstaticマウント（/static/{job_id}/...）
if RESULTS_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(RESULTS_DIR)), name="static")

# viewer.html用のstaticマウント（/viewer.html）
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static-files", StaticFiles(directory=str(static_dir)), name="static-files")

# ジョブ管理
jobs: Dict[str, Dict[str, Any]] = {}

# 処理用のスレッドプール（Webサーバーをブロックしないように別スレッドで処理）
# max_workers=2: 同時に2つのジョブを処理可能
PROCESSING_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="processing_")

# ジョブデータの永続化
JOBS_DB_PATH = DATA_DIR / "jobs_db.json"

def load_jobs_from_disk():
    """ディスクからジョブ情報を読み込む"""
    global jobs
    if JOBS_DB_PATH.exists():
        try:
            with open(JOBS_DB_PATH, 'r') as f:
                jobs = json.load(f)
            print(f"Loaded {len(jobs)} jobs from disk")
        except Exception as e:
            print(f"Failed to load jobs from disk: {e}")
            jobs = {}

def save_jobs_to_disk():
    """ジョブ情報をディスクに保存"""
    try:
        with open(JOBS_DB_PATH, 'w') as f:
            json.dump(jobs, f, indent=2)
    except Exception as e:
        print(f"Failed to save jobs to disk: {e}")

# 起動時にジョブを読み込み
load_jobs_from_disk()

# 処理設定
PROCESSING_CONFIG = CONFIG.get('processing', {})
DEFAULT_MODE = PROCESSING_CONFIG.get('default_mode', 'rgbd')

# GPU設定
GPU_CONFIG = CONFIG.get('gpu', {})
DEPTH_ESTIMATION_CONFIG = CONFIG.get('depth_estimation', {})

# GPU情報を表示
if GPU_CONFIG.get('enabled', True):
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            current_device = GPU_CONFIG.get('device_id', 0)
            gpu_name = torch.cuda.get_device_name(current_device)
            print(f"GPU: {gpu_name} (Device {current_device}/{gpu_count-1})")
        else:
            print("GPU: CUDA not available")
    except ImportError:
        print("GPU: PyTorch not installed")

print(f"ARCore + Open3D Server initialized")
print(f"  Data dir: {DATA_DIR}")
print(f"  Default mode: {DEFAULT_MODE}")
print(f"  GPU enabled: {GPU_CONFIG.get('enabled', True)}")

# ============================================================
# API エンドポイント
# ============================================================

@app.get("/")
async def root():
    """サーバーステータス"""
    return {
        "service": "ARCore + Open3D 3D Reconstruction Server",
        "status": "running",
        "default_mode": DEFAULT_MODE,
        "available_modes": ["rgbd", "pointcloud"],
        "jobs_count": len(jobs),
        "open3d_version": o3d.__version__
    }

@app.get("/api/v1/health")
async def health():
    """ヘルスチェック"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/v1/config")
async def get_config():
    """現在の設定を取得"""
    return {
        "default_mode": DEFAULT_MODE,
        "processing": PROCESSING_CONFIG,
        "mesh": CONFIG.get('mesh', {})
    }

@app.get("/viewer")
@app.get("/viewer/{job_id}")
async def viewer(job_id: str = None):
    """3D Viewer"""
    # static/viewer.htmlを優先的に使用
    viewer_path = Path(__file__).parent / "static" / "viewer.html"
    if not viewer_path.exists():
        # フォールバック: viewer/index.html
        viewer_path = Path(__file__).parent / "viewer" / "index.html"
    
    if viewer_path.exists():
        return FileResponse(viewer_path, media_type="text/html")
    else:
        return HTMLResponse("<h1>Viewer not found. Please check if static/viewer.html exists.</h1>")

@app.post("/api/v1/sessions/upload")
async def upload_session(
    background_tasks: BackgroundTasks,
    metadata: UploadFile = File(...),
    intrinsics: UploadFile = File(...),
    poses: UploadFile = File(...),
    rfid: UploadFile = File(None),
    images: List[UploadFile] = File(...),
    depths: List[UploadFile] = File(None),  # Depthデータ（オプション）
    mode: str = None  # "rgbd" or "pointcloud"
):
    """
    ARCoreセッションデータをアップロード
    """
    job_id = str(uuid.uuid4())[:8]
    
    try:
        # 必須パラメータの確認とログ
        print(f"[{job_id}] Received upload request")
        print(f"[{job_id}]   metadata: {metadata.filename if metadata else 'None'}")
        print(f"[{job_id}]   intrinsics: {intrinsics.filename if intrinsics else 'None'}")
        print(f"[{job_id}]   poses: {poses.filename if poses else 'None'}")
        print(f"[{job_id}]   images: {len(images) if images else 0}")
        print(f"[{job_id}]   depths: {len(depths) if depths else 0}")
        print(f"[{job_id}]   rfid: {rfid.filename if rfid else 'None'}")
        print(f"[{job_id}]   mode: {mode}")
        
        if not metadata:
            raise HTTPException(status_code=400, detail="metadata is required")
        if not intrinsics:
            raise HTTPException(status_code=400, detail="intrinsics is required")
        if not poses:
            raise HTTPException(status_code=400, detail="poses is required")
        if not images or len(images) == 0:
            raise HTTPException(status_code=400, detail="at least one image is required")
        
        session_dir = SESSIONS_DIR / job_id
        session_dir.mkdir(parents=True, exist_ok=True)
        images_dir = session_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        processing_mode = mode if mode in ["rgbd", "pointcloud"] else DEFAULT_MODE
        
        # ファイル保存
        async with aiofiles.open(session_dir / "metadata.json", "wb") as f:
            await f.write(await metadata.read())
        async with aiofiles.open(session_dir / "camera_intrinsics.json", "wb") as f:
            await f.write(await intrinsics.read())
        async with aiofiles.open(session_dir / "ARCore_sensor_pose.txt", "wb") as f:
            await f.write(await poses.read())
        if rfid:
            async with aiofiles.open(session_dir / "rfid_detections.json", "wb") as f:
                await f.write(await rfid.read())
        
        # 画像保存
        for img in images:
            async with aiofiles.open(images_dir / img.filename, "wb") as f:
                await f.write(await img.read())
        
        # Depth保存（存在する場合）
        has_depth = False
        if depths:
            depth_dir = session_dir / "depth"
            depth_dir.mkdir(exist_ok=True)
            for depth in depths:
                async with aiofiles.open(depth_dir / depth.filename, "wb") as f:
                    await f.write(await depth.read())
            has_depth = True
        
        # ジョブ登録
        jobs[job_id] = {
            "status": "queued",
            "progress": 0,
            "image_count": len(images),
            "has_depth": has_depth,
            "mode": processing_mode,
            "created_at": datetime.now().isoformat(),
            "current_step": "queued"
        }
        
        # ディスクに保存
        save_jobs_to_disk()
        
        # バックグラウンド処理開始
        background_tasks.add_task(process_session, job_id, session_dir)
        
        print(f"[{job_id}] Upload successful, job queued")
        
        return {
            "job_id": job_id,
            "status": "queued",
            "image_count": len(images),
            "has_depth": has_depth,
            "mode": processing_mode,
            "message": f"Processing started. Check status at /api/v1/jobs/{job_id}/status"
        }
    except HTTPException:
        print(f"[{job_id}] HTTPException raised")
        raise
    except Exception as e:
        print(f"[{job_id}] Error in upload_session: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")

@app.get("/api/v1/jobs/{job_id}/status")
async def get_status(job_id: str):
    """ジョブステータス取得"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/api/v1/jobs")
async def list_jobs():
    """全ジョブ一覧"""
    return {"jobs": jobs, "count": len(jobs)}

@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    """ジョブ削除"""
    if job_id in jobs:
        del jobs[job_id]
        session_dir = SESSIONS_DIR / job_id
        result_dir = RESULTS_DIR / job_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
        if result_dir.exists():
            shutil.rmtree(result_dir)
        return {"status": "deleted"}
    raise HTTPException(404, "Job not found")

# ============================================================
# 結果ファイル配信
# ============================================================

@app.get("/scenes/{job_id}/point_cloud.ply")
async def get_point_cloud(job_id: str):
    """点群PLYファイル"""
    path = RESULTS_DIR / job_id / "point_cloud.ply"
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/octet-stream")

@app.get("/scenes/{job_id}/mesh.ply")
async def get_mesh(job_id: str):
    """メッシュPLYファイル"""
    path = RESULTS_DIR / job_id / "mesh.ply"
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path, media_type="application/octet-stream")

@app.get("/scenes/{job_id}/rfid_positions.json")
async def get_rfid(job_id: str):
    """RFIDポジションJSON"""
    path = RESULTS_DIR / job_id / "rfid_positions.json"
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)

@app.get("/scenes/{job_id}/trajectory.json")
async def get_trajectory(job_id: str):
    """カメラ軌跡JSON（ARCoreポーズから生成）"""
    # まず保存済みのtrajectory.jsonを確認
    trajectory_path = RESULTS_DIR / job_id / "trajectory.json"
    if trajectory_path.exists():
        return FileResponse(trajectory_path)
    
    # 無ければARCoreポーズから生成
    session_dir = SESSIONS_DIR / job_id
    pose_file = session_dir / "ARCore_sensor_pose.txt"
    
    if not pose_file.exists():
        raise HTTPException(404, "Pose data not found")
    
    poses = []
    try:
        with open(pose_file, 'r') as f:
            prev_pos = None
            for line in f:
                if line.startswith('#'):
                    continue
                parts = line.strip().split()
                if len(parts) >= 4:
                    try:
                        x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                        # 重複を除去
                        if prev_pos is None or (abs(x - prev_pos[0]) > 0.001 or abs(y - prev_pos[1]) > 0.001 or abs(z - prev_pos[2]) > 0.001):
                            # 座標変換（COLMAP→viewer座標系）: X軸周りに180度回転
                            poses.append({"x": x, "y": -y, "z": -z})
                            prev_pos = (x, y, z)
                    except ValueError:
                        continue
        
        # 保存
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trajectory_path, 'w') as f:
            json.dump({"poses": poses, "count": len(poses)}, f)
        
        return {"poses": poses, "count": len(poses)}
    except Exception as e:
        raise HTTPException(500, f"Error reading pose data: {str(e)}")

@app.get("/scenes/{job_id}/info.json")
async def get_scene_info(job_id: str):
    """シーン情報"""
    result_dir = RESULTS_DIR / job_id
    
    # ジョブ情報を取得（メモリまたはディスクから）
    if job_id not in jobs:
        # ディスクから読み込みを試みる
        load_jobs_from_disk()
        if job_id not in jobs:
            # 結果ディレクトリが存在する場合は、基本的な情報を返す
            if not result_dir.exists():
                raise HTTPException(404, "Job not found")
            
            # ファイルの存在確認のみ
            available_files = {}
            for filename in ["point_cloud.ply", "mesh.ply", "rfid_positions.json"]:
                path = result_dir / filename
                available_files[filename] = path.exists()
            
            # ビューアー設定を取得
            viewer_config = CONFIG.get('viewer', {})
            auto_load_config = viewer_config.get('auto_load', {})
            default_view = viewer_config.get('default_view', 'mesh')
            
            return {
                "job_id": job_id,
                "status": "completed",  # 結果ファイルが存在するので完了とみなす
                "mode": "unknown",
                "available_files": available_files,
                "result": {},
                "viewer_config": {
                    "default_view": default_view,
                    "auto_load": {
                        "point_cloud": auto_load_config.get('point_cloud', False),
                        "mesh": auto_load_config.get('mesh', True),
                        "rfid": auto_load_config.get('rfid', True)
                    }
                }
            }
    
    job = jobs[job_id]
    
    available_files = {}
    for filename in ["point_cloud.ply", "mesh.ply", "rfid_positions.json"]:
        path = result_dir / filename
        available_files[filename] = path.exists()
    
    # ビューアー設定を取得
    viewer_config = CONFIG.get('viewer', {})
    auto_load_config = viewer_config.get('auto_load', {})
    default_view = viewer_config.get('default_view', 'mesh')
    
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "mode": job.get("mode"),
        "available_files": available_files,
        "result": job.get("result", {}),
        "viewer_config": {
            "default_view": default_view,
            "auto_load": {
                "point_cloud": auto_load_config.get('point_cloud', False),
                "mesh": auto_load_config.get('mesh', True),
                "rfid": auto_load_config.get('rfid', True)
            }
        }
    }

# ============================================================
# 処理パイプライン
# ============================================================

def _process_session_sync(job_id: str, session_dir: Path):
    """セッションを処理（同期版 - 別スレッドで実行される）"""
    try:
        jobs[job_id]["status"] = "processing"
        result_dir = RESULTS_DIR / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        
        # デフォルトモードをconfig.yamlから取得
        default_mode = PROCESSING_CONFIG.get('default_mode', 'rgbd')
        mode = jobs[job_id].get("mode") or default_mode
        
        # ステップ1: データ解析
        update_job(job_id, 5, "parsing", "Parsing session data...")
        
        parser = ARCoreDataParser(session_dir)
        if not parser.parse():
            raise ValueError("Failed to parse session data")
        
        print(f"[{job_id}] Frames: {len(parser.frames)}, Has depth: {parser.has_depth_data()}")
        
        # 深度推定の強制使用オプション（GPU使用のため）
        force_depth_estimation = DEPTH_ESTIMATION_CONFIG.get('force_use', False)
        use_depth_estimation = not parser.has_depth_data() or force_depth_estimation
        
        # ステップ2: 3D再構成
        pcd = None
        mesh = None
        
        # MVS（COLMAP）パイプラインを使用する場合
        if mode == "mvs":
            # MVS (COLMAP) Pipeline
            update_job(job_id, 10, "mvs_pipeline", "MVS pipeline (COLMAP)...")
            
            try:
                from pipeline.colmap_mvs import COLMAPMVSPipeline
                
                mvs_pipeline = COLMAPMVSPipeline(CONFIG, GPU_CONFIG)
                
                def progress_cb(p, m):
                    overall = 10 + int(p * 0.8)
                    update_job(job_id, overall, "mvs_pipeline", m)
                
                pcd, mesh = mvs_pipeline.process_session(
                    parser,
                    session_dir,
                    result_dir,
                    progress_cb
                )
                
                if pcd is None or len(pcd.points) == 0:
                    print(f"[{job_id}] ⚠ Warning: MVS point cloud is empty!")
                    pcd = None
                else:
                    print(f"[{job_id}] MVS point cloud: {len(pcd.points)} points")
                
                if mesh is None or len(mesh.triangles) == 0:
                    print(f"[{job_id}] ⚠ Warning: MVS mesh is empty!")
                    mesh = None
                else:
                    print(f"[{job_id}] MVS mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                    
            except ImportError as e:
                print(f"[{job_id}] Error importing COLMAP MVS pipeline: {e}")
                print(f"[{job_id}] Falling back to RGB-D integration...")
                mode = "rgbd"
            except Exception as e:
                print(f"[{job_id}] MVS pipeline error: {e}")
                import traceback
                traceback.print_exc()
                print(f"[{job_id}] Falling back to RGB-D integration...")
                mode = "rgbd"
        
        # RGB-D Integration（従来の方式、またはMVSが失敗した場合のフォールバック）
        if mode == "rgbd" and (parser.has_depth_data() or use_depth_estimation) and (pcd is None or mesh is None):
            # RGB-D Integration (GPU対応)
            update_job(job_id, 10, "rgbd_integration", "RGB-D integration (GPU)...")
            
            # GPU対応版を使用（GPU設定を渡す）
            if GPU_AVAILABLE:
                integration = RGBDIntegration(PROCESSING_CONFIG, GPU_CONFIG)
            else:
                # CPU版を使用（後方互換性のため）
                integration = RGBDIntegration(PROCESSING_CONFIG)
            
            def progress_cb(p, m):
                overall = 10 + int(p * 0.5)
                update_job(job_id, overall, "rgbd_integration", m)
            
            try:
                # 深度推定の強制使用（GPU使用のため）
                if integration.process_session(parser, progress_cb, force_depth_estimation=use_depth_estimation):
                    update_job(job_id, 65, "extracting", "Extracting point cloud and mesh...")
                    # GPU対応版の関数を使用
                    if GPU_AVAILABLE:
                        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG, GPU_CONFIG)
                    else:
                        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG)
                    
                    # 点群とメッシュの確認
                    if pcd is not None:
                        print(f"[{job_id}] Extracted point cloud: {len(pcd.points)} points")
                        if len(pcd.points) == 0:
                            print(f"[{job_id}] ⚠ Warning: Point cloud is empty!")
                            pcd = None
                    else:
                        print(f"[{job_id}] ⚠ Warning: Failed to extract point cloud")
                    
                    if mesh is not None:
                        print(f"[{job_id}] Extracted mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                        if len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
                            print(f"[{job_id}] ⚠ Warning: Mesh is empty!")
                            mesh = None
                    else:
                        print(f"[{job_id}] ⚠ Warning: Failed to extract mesh")
                    
                    # 点群が空の場合、Volumeから直接点群を抽出
                    if pcd is None or len(pcd.points) == 0:
                        print(f"[{job_id}] Attempting to extract point cloud directly from volume...")
                        try:
                            pcd = integration.extract_point_cloud()
                            if pcd is not None and len(pcd.points) > 0:
                                print(f"[{job_id}] Successfully extracted point cloud: {len(pcd.points)} points")
                            else:
                                print(f"[{job_id}] ⚠ Point cloud extraction failed or empty")
                        except Exception as e:
                            print(f"[{job_id}] Error extracting point cloud: {e}")
                    
                    # メッシュが空の場合、Volumeから直接メッシュを抽出
                    if mesh is None or (len(mesh.vertices) == 0 or len(mesh.triangles) == 0):
                        print(f"[{job_id}] Attempting to extract mesh directly from volume...")
                        try:
                            mesh = integration.extract_mesh()
                            if mesh is not None and len(mesh.vertices) > 0 and len(mesh.triangles) > 0:
                                print(f"[{job_id}] Successfully extracted mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                            else:
                                print(f"[{job_id}] ⚠ Mesh extraction failed or empty")
                        except Exception as e:
                            print(f"[{job_id}] Error extracting mesh: {e}")
                    
                    # Volumeを明示的に解放してメモリを節約
                    integration.volume = None
                    import gc
                    gc.collect()
                    print(f"[{job_id}] Volume released, memory freed")
            except MemoryError as e:
                print(f"[{job_id}] Memory error during RGB-D integration: {e}")
                print(f"[{job_id}] Try increasing voxel_length in config.yaml to reduce memory usage")
                # Volumeを解放
                if hasattr(integration, 'volume'):
                    integration.volume = None
                import gc
                gc.collect()
                raise
                
        else:
            # Point Cloud Fusion (Depthなし)
            update_job(job_id, 10, "pointcloud_fusion", "Point cloud fusion...")
            
            # この場合は画像から直接点群を作成できないので、
            # Monocular Depth Estimationが必要
            # 今回は仮の処理
            print(f"[{job_id}] No depth data, using fallback")
            
            # ポーズから軌跡を点群として出力（デモ用）
            points = []
            for frame in parser.get_frames_with_pose():
                pose = frame.pose.to_matrix()
                points.append(pose[:3, 3])
            
            if points:
                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(np.array(points))
                pcd.paint_uniform_color([0, 0.5, 1])
        
        # ステップ3: メッシュ生成（点群のみの場合）
        # 点群が存在し、メッシュが生成されていない場合
        if pcd is not None and len(pcd.points) > 0:
            if mesh is None or len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
                # 点群が少ない場合でもメッシュ生成を試みる（最小10点）
                if len(pcd.points) >= 10:
                    update_job(job_id, 70, "mesh_generation", f"Generating mesh from {len(pcd.points)} points (GPU)...")
                    
                    # GPU対応版を使用
                    if GPU_AVAILABLE:
                        mesh_gen = MeshGenerator(CONFIG.get('mesh', {}), GPU_CONFIG)
                    else:
                        mesh_gen = MeshGenerator(CONFIG.get('mesh', {}))
                    mesh = mesh_gen.generate(pcd)
                    
                    if mesh is not None and len(mesh.vertices) > 0:
                        print(f"[{job_id}] Generated mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                    else:
                        print(f"[{job_id}] ⚠ Mesh generation failed or produced empty mesh")
                else:
                    print(f"[{job_id}] ⚠ Not enough points for mesh generation: {len(pcd.points)} < 10")
        
        # ステップ4: 結果保存
        update_job(job_id, 85, "saving", "Saving results...")
        
        # 点群の保存（点群が存在し、点が1つ以上ある場合）
        if pcd is not None and len(pcd.points) > 0:
            pcd_path = result_dir / "point_cloud.ply"
            try:
                # 点群に色がなければ追加（視認性向上）
                if not pcd.has_colors():
                    # 点群の位置に基づいて色を付ける（視認性向上）
                    points = np.asarray(pcd.points)
                    if len(points) > 0:
                        # Z軸の高さに基づいて色を付ける
                        z_min = points[:, 2].min()
                        z_max = points[:, 2].max()
                        if z_max > z_min:
                            z_normalized = (points[:, 2] - z_min) / (z_max - z_min)
                            # カラーマップ: 青→緑→黄→赤
                            colors = np.zeros((len(points), 3))
                            colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                            colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                            colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                            pcd.colors = o3d.utility.Vector3dVector(colors)
                        else:
                            # 単色（青）
                            pcd.paint_uniform_color([0.2, 0.5, 1.0])
                    else:
                        pcd.paint_uniform_color([0.2, 0.5, 1.0])
                
                o3d.io.write_point_cloud(str(pcd_path), pcd)
                print(f"[{job_id}] ✓ Saved point cloud: {len(pcd.points)} points")
            except Exception as e:
                print(f"[{job_id}] ✗ Error saving point cloud: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[{job_id}] ⚠ No point cloud to save (pcd is None or empty)")
        
        # メッシュの保存（メッシュが存在し、頂点と三角形がある場合）
        if mesh is not None and len(mesh.vertices) > 0 and len(mesh.triangles) > 0:
            mesh_path = result_dir / "mesh.ply"
            try:
                # メッシュに色がなければ追加（視認性向上）
                if not mesh.has_vertex_colors():
                    # 頂点の位置に基づいて色を付ける
                    vertices = np.asarray(mesh.vertices)
                    if len(vertices) > 0:
                        z_min = vertices[:, 2].min()
                        z_max = vertices[:, 2].max()
                        if z_max > z_min:
                            z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                            colors = np.zeros((len(vertices), 3))
                            colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)
                            colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)
                            colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)
                            mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                        else:
                            mesh.paint_uniform_color([0.7, 0.7, 0.7])
                    else:
                        mesh.paint_uniform_color([0.7, 0.7, 0.7])
                
                # メッシュの品質向上処理
                print(f"[{job_id}] Improving mesh quality...")
                
                # 1. メッシュのクリーンアップ
                mesh.remove_duplicated_triangles()
                mesh.remove_duplicated_vertices()
                mesh.remove_non_manifold_edges()
                mesh.remove_degenerate_triangles()
                mesh.remove_unreferenced_vertices()
                
                # 2. メッシュの平滑化（簡略化前に行う、yaml設定を適用）
                mesh_config = CONFIG.get('mesh', {})
                smoothing_config = mesh_config.get('smoothing', {})
                if smoothing_config.get('enable', True):
                    iterations = smoothing_config.get('iterations', 5)
                    lambda_filter = smoothing_config.get('lambda_filter', 0.5)
                    method = smoothing_config.get('method', 'laplacian')
                    
                    print(f"[{job_id}] Smoothing mesh ({method}, {iterations} iterations, lambda={lambda_filter})...")
                    try:
                        if method == 'laplacian':
                            mesh = mesh.filter_smooth_laplacian(
                                number_of_iterations=iterations,
                                lambda_filter=lambda_filter
                            )
                        elif method == 'taubin':
                            # Taubin平滑化（Open3D 0.19以降で利用可能）
                            mesh = mesh.filter_smooth_taubin(
                                number_of_iterations=iterations,
                                lambda_filter=lambda_filter,
                                mu=-0.53  # Taubinパラメータ（推奨値）
                            )
                        else:
                            print(f"[{job_id}] ⚠ Unknown smoothing method: {method}, using laplacian")
                            mesh = mesh.filter_smooth_laplacian(
                                number_of_iterations=iterations,
                                lambda_filter=lambda_filter
                            )
                        mesh.compute_vertex_normals()
                        print(f"[{job_id}] ✓ Mesh smoothed")
                    except Exception as e:
                        print(f"[{job_id}] ⚠ Smoothing error: {e}")
                
                # 3. メッシュ品質向上処理（細分化、法線改善、色補正）
                quality_config = mesh_config.get('quality_improvement', {})
                if quality_config.get('enable', True):
                    # 3-1. メッシュ細分化（Subdivision）- 多様体チェックとメモリ保護付き
                    subdivision_config = quality_config.get('subdivision', {})
                    if subdivision_config.get('enable', True):
                        subdiv_method = subdivision_config.get('method', 'loop')
                        subdiv_iterations = subdivision_config.get('iterations', 1)
                        
                        if subdiv_iterations > 0:
                            # メモリ保護: 大きなメッシュの場合は細分化をスキップ
                            triangle_count = len(mesh.triangles)
                            if triangle_count > 3000000:  # 300万三角形以上は細分化をスキップ
                                print(f"[{job_id}] ⚠ Large mesh ({triangle_count} triangles), skipping subdivision to prevent memory issues")
                                subdiv_iterations = 0
                            
                            if subdiv_iterations > 0:
                                print(f"[{job_id}] Checking mesh manifoldness before subdivision...")
                                try:
                                    # メッシュの多様体性を確認
                                    is_edge_manifold = mesh.is_edge_manifold(allow_boundary_edges=True)
                                    is_vertex_manifold = mesh.is_vertex_manifold()
                                    
                                    if not is_edge_manifold or not is_vertex_manifold:
                                        print(f"[{job_id}] ⚠ Mesh is not manifold (edge_manifold: {is_edge_manifold}, vertex_manifold: {is_vertex_manifold})")
                                        print(f"[{job_id}]   Attempting to fix non-manifold mesh...")
                                        
                                        # 非多様体メッシュの修正（より強力な手法）
                                        # 1. 重複三角形・頂点の削除
                                        mesh.remove_duplicated_triangles()
                                        mesh.remove_duplicated_vertices()
                                        mesh.remove_unreferenced_vertices()
                                        
                                        # 2. 非多様体エッジの削除（複数回実行）
                                        for _ in range(3):
                                            mesh.remove_non_manifold_edges()
                                            mesh.remove_duplicated_triangles()
                                            mesh.remove_duplicated_vertices()
                                            mesh.remove_unreferenced_vertices()
                                        
                                        # 3. 退化三角形の削除
                                        try:
                                            mesh.remove_degenerate_triangles()
                                        except AttributeError:
                                            # Open3Dのバージョンによっては利用できない場合がある
                                            pass
                                        
                                        # 4. 法線の再計算
                                        mesh.compute_vertex_normals()
                                        
                                        # 再度確認
                                        is_edge_manifold = mesh.is_edge_manifold(allow_boundary_edges=True)
                                        is_vertex_manifold = mesh.is_vertex_manifold()
                                        
                                        if not is_edge_manifold or not is_vertex_manifold:
                                            print(f"[{job_id}] ⚠ Mesh is still not manifold after cleanup, skipping subdivision to prevent errors")
                                            print(f"[{job_id}]   Note: Non-manifold mesh may still work for visualization, but subdivision requires manifold mesh")
                                            subdiv_iterations = 0
                                        else:
                                            print(f"[{job_id}] ✓ Mesh is now manifold, proceeding with subdivision")
                                    
                                    if subdiv_iterations > 0:
                                        # 反復回数を制限（メモリ保護）
                                        max_iterations = subdivision_config.get('max_iterations', 1)
                                        subdiv_iterations = min(subdiv_iterations, max_iterations)
                                        
                                        print(f"[{job_id}] Subdividing mesh ({subdiv_method}, {subdiv_iterations} iterations)...")
                                        
                                        if subdiv_method == 'loop':
                                            mesh = mesh.subdivide_loop(number_of_iterations=subdiv_iterations)
                                        elif subdiv_method == 'midpoint':
                                            mesh = mesh.subdivide_midpoint(number_of_iterations=subdiv_iterations)
                                        else:
                                            print(f"[{job_id}] ⚠ Unknown subdivision method: {subdiv_method}, using loop")
                                            mesh = mesh.subdivide_loop(number_of_iterations=subdiv_iterations)
                                        
                                        # 細分化後のクリーンアップ
                                        mesh.remove_duplicated_triangles()
                                        mesh.remove_duplicated_vertices()
                                        mesh.remove_non_manifold_edges()
                                        mesh.compute_vertex_normals()
                                        
                                        print(f"[{job_id}] ✓ Mesh subdivided: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                                except Exception as e:
                                    print(f"[{job_id}] ⚠ Subdivision error: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    # エラーが発生した場合は細分化をスキップして続行
                    
                    # 3-2. 法線の改善
                    normal_config = quality_config.get('normal_improvement', {})
                    if normal_config.get('enable', True):
                        print(f"[{job_id}] Improving normals...")
                        try:
                            # より高品質な法線計算
                            mesh.compute_vertex_normals(
                                normalized=True
                            )
                            if normal_config.get('smooth_normals', True):
                                # 法線の平滑化（オプション）
                                mesh.normalize_normals()
                            print(f"[{job_id}] ✓ Normals improved")
                        except Exception as e:
                            print(f"[{job_id}] ⚠ Normal improvement error: {e}")
                    
                    # 3-3. 色の補正と強化
                    color_config = quality_config.get('color_enhancement', {})
                    if color_config.get('enable', True) and mesh.has_vertex_colors():
                        print(f"[{job_id}] Enhancing colors...")
                        try:
                            colors = np.asarray(mesh.vertex_colors)
                            contrast = color_config.get('contrast', 1.0)
                            saturation = color_config.get('saturation', 1.0)
                            brightness = color_config.get('brightness', 1.0)
                            
                            # コントラスト調整
                            if contrast != 1.0:
                                colors = (colors - 0.5) * contrast + 0.5
                            
                            # 彩度調整（HSV変換）
                            if saturation != 1.0:
                                # RGB to HSV
                                hsv = np.zeros_like(colors)
                                max_val = colors.max(axis=1, keepdims=True)
                                min_val = colors.min(axis=1, keepdims=True)
                                delta = max_val - min_val
                                
                                # Saturation adjustment
                                hsv[:, 1] = np.clip(delta[:, 0] * saturation, 0, 1)
                                hsv[:, 2] = max_val[:, 0]  # Value
                                
                                # 簡易的な彩度調整（より簡単な方法）
                                gray = np.mean(colors, axis=1, keepdims=True)
                                colors = gray + (colors - gray) * saturation
                            
                            # 明度調整
                            if brightness != 1.0:
                                colors = colors * brightness
                            
                            colors = np.clip(colors, 0, 1)
                            mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                            print(f"[{job_id}] ✓ Colors enhanced (contrast={contrast}, saturation={saturation}, brightness={brightness})")
                        except Exception as e:
                            print(f"[{job_id}] ⚠ Color enhancement error: {e}")
                
                # 3. メッシュが大きすぎる場合は簡略化（ビューアー用、設定でON/OFF可能）
                output_config = CONFIG.get('output', {})
                mesh_output_config = output_config.get('mesh', {})
                simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)  # デフォルト: true
                max_triangles = mesh_output_config.get('max_triangles_for_viewer', 1000000)  # 100万三角形まで
                
                original_triangles = len(mesh.triangles)
                mesh_to_save = mesh
                
                # 簡略化する前に元のメッシュを保存
                original_mesh_path = result_dir / "mesh_original.ply"
                save_original = False
                
                if simplify_for_viewer and original_triangles > max_triangles:
                    print(f"[{job_id}] ⚠ Mesh too large ({original_triangles} triangles), simplifying to {max_triangles} for viewer...")
                    # 簡略化前に元のメッシュを保存
                    try:
                        o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
                        save_original = True
                        print(f"[{job_id}] ✓ Saved original mesh (before simplification): {original_triangles} triangles")
                    except Exception as e:
                        print(f"[{job_id}] ⚠ Failed to save original mesh: {e}")
                    
                    try:
                        # 簡略化（品質を保ちながら）
                        mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
                        if len(mesh_simplified.triangles) > 0:
                            # 簡略化後もクリーンアップ
                            mesh_simplified.remove_duplicated_triangles()
                            mesh_simplified.remove_duplicated_vertices()
                            mesh_simplified.remove_non_manifold_edges()
                            mesh_simplified.compute_vertex_normals()
                            
                            mesh_to_save = mesh_simplified
                            print(f"[{job_id}] ✓ Simplified mesh: {len(mesh_simplified.triangles)} triangles ({original_triangles} -> {len(mesh_simplified.triangles)})")
                        else:
                            print(f"[{job_id}] ⚠ Simplification failed, using original mesh")
                    except Exception as e:
                        print(f"[{job_id}] ⚠ Simplification error: {e}, using original mesh")
                elif not simplify_for_viewer:
                    print(f"[{job_id}] ℹ Viewer simplification is disabled (simplify_for_viewer=false), using original mesh ({original_triangles} triangles)")
                
                # メッシュを保存（ASCII形式で保存、Three.jsのPLYLoaderと互換性がある）
                # 注意: 大きなメッシュの場合はASCII形式でもファイルサイズが大きくなる
                try:
                    # まず簡略化されたメッシュをASCII形式で保存
                    o3d.io.write_triangle_mesh(
                        str(mesh_path), 
                        mesh_to_save,
                        write_ascii=True,
                        compressed=False
                    )
                    mesh_info = MeshGenerator.get_mesh_info(mesh_to_save)
                    print(f"[{job_id}] ✓ Saved mesh (ASCII): {mesh_info['vertices']} vertices, {mesh_info['triangles']} triangles")
                except Exception as e:
                    print(f"[{job_id}] ⚠ ASCII save failed: {e}, trying binary format...")
                    # ASCII形式で保存できない場合はバイナリ形式で保存
                    o3d.io.write_triangle_mesh(str(mesh_path), mesh_to_save)
                    mesh_info = MeshGenerator.get_mesh_info(mesh_to_save)
                    print(f"[{job_id}] ✓ Saved mesh (Binary): {mesh_info['vertices']} vertices, {mesh_info['triangles']} triangles")
                    
            except Exception as e:
                print(f"[{job_id}] ✗ Error saving mesh: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[{job_id}] ⚠ No mesh to save (mesh is None or empty)")
            if mesh is not None:
                print(f"[{job_id}]   Mesh status: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
        
        # RFID位置を保存
        export_rfid_positions(parser, result_dir)
        
        # 完了
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["current_step"] = "done"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        # Depth sourceの判定
        depth_source = "Unknown"
        if use_depth_estimation and force_depth_estimation:
            depth_source = "MiDaS_DPT_Large"
        elif use_depth_estimation:
            depth_source = "MiDaS_DPT_Large"
        elif parser.has_depth_data():
            # ARCore Depthの種類を判定（実際のデータから判定するのは困難なため、推定）
            # ARCore Depthには複数のソースがある: Depth Camera, Motion Stereo, ML-based estimation
            depth_source = "ARCore_Depth"
        else:
            depth_source = "None"
        
        jobs[job_id]["result"] = {
            "point_cloud_url": f"/scenes/{job_id}/point_cloud.ply",
            "mesh_url": f"/scenes/{job_id}/mesh.ply" if mesh else None,
            "rfid_positions_url": f"/scenes/{job_id}/rfid_positions.json",
            "viewer_url": f"/viewer/{job_id}",
            "point_count": len(pcd.points) if pcd and len(pcd.points) > 0 else 0,
            "mesh_info": MeshGenerator.get_mesh_info(mesh) if mesh and len(mesh.vertices) > 0 else None,
            "gpu_accelerated": GPU_AVAILABLE,
            "has_point_cloud": pcd is not None and len(pcd.points) > 0,
            "has_mesh": mesh is not None and len(mesh.vertices) > 0 and len(mesh.triangles) > 0,
            "depth_source": depth_source,
            "has_depth": parser.has_depth_data(),
            "frames_with_depth": len(parser.get_frames_with_depth()),
            "total_frames": len(parser.frames)
        }
        
        # ディスクに保存
        save_jobs_to_disk()
        
        print(f"[{job_id}] ✅ Job completed")
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["failed_at"] = datetime.now().isoformat()
        
        # ディスクに保存
        save_jobs_to_disk()
        
        print(f"[{job_id}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def process_session(job_id: str, session_dir: Path):
    """セッションを処理（非同期ラッパー - 別スレッドで実行）
    
    重い処理をThreadPoolExecutorで実行することで、
    Webサーバー（FastAPI）がブロックされずに他のリクエストを処理できる。
    これにより、処理中でもviewerにアクセス可能になる。
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        PROCESSING_EXECUTOR,
        _process_session_sync,
        job_id,
        session_dir
    )


def update_job(job_id: str, progress: int, step: str, message: str = ""):
    """ジョブステータス更新"""
    jobs[job_id]["progress"] = progress
    jobs[job_id]["current_step"] = step
    if message:
        jobs[job_id]["message"] = message


def export_rfid_positions(parser: ARCoreDataParser, result_dir: Path):
    """RFID位置をエクスポート"""
    rfid_data = {
        "detections": [],
        "unique_tags": parser.get_unique_rfid_tags()
    }
    
    for detection in parser.rfid_detections:
        d = {
            "tag_id": detection.tag_id,
            "timestamp": detection.timestamp,
            "rssi": detection.rssi
        }
        if detection.pose:
            d["position"] = {
                "x": detection.pose.tx,
                "y": detection.pose.ty,
                "z": detection.pose.tz
            }
        rfid_data["detections"].append(d)
    
    rfid_path = result_dir / "rfid_positions.json"
    with open(rfid_path, 'w') as f:
        json.dump(rfid_data, f, indent=2)


# ============================================================
# エントリーポイント
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 8000)
    
    # 大きなファイルアップロードに対応
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        timeout_keep_alive=300,  # 5分間のキープアライブ
        limit_max_requests=None,
    )
