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
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

import numpy as np
import open3d as o3d

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import aiofiles

# パイプライン
from utils.arcore_parser import ARCoreDataParser
from pipeline.rgbd_integration import RGBDIntegration, PointCloudFusion
from pipeline.mesh_generation import MeshGenerator, create_mesh_from_rgbd_volume

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ディレクトリ設定
server_config = CONFIG.get('server', {})
DATA_DIR = Path(server_config.get('data_dir', '/opt/arcore-3dmapper-open3d/data'))
SESSIONS_DIR = DATA_DIR / "sessions"
RESULTS_DIR = DATA_DIR / "results"

SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# 静的ファイル配信
if RESULTS_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(RESULTS_DIR)), name="static")

# ジョブ管理
jobs: Dict[str, Dict[str, Any]] = {}

# 処理設定
PROCESSING_CONFIG = CONFIG.get('processing', {})
DEFAULT_MODE = PROCESSING_CONFIG.get('default_mode', 'rgbd')

print(f"ARCore + Open3D Server initialized")
print(f"  Data dir: {DATA_DIR}")
print(f"  Default mode: {DEFAULT_MODE}")

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
    viewer_path = Path(__file__).parent / "viewer" / "index.html"
    if viewer_path.exists():
        return FileResponse(viewer_path, media_type="text/html")
    else:
        return HTMLResponse("<h1>Viewer not found</h1>")

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
    
    # バックグラウンド処理開始
    background_tasks.add_task(process_session, job_id, session_dir)
    
    return {
        "job_id": job_id,
        "status": "queued",
        "image_count": len(images),
        "has_depth": has_depth,
        "mode": processing_mode,
        "message": f"Processing started. Check status at /api/v1/jobs/{job_id}/status"
    }

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

@app.get("/scenes/{job_id}/info.json")
async def get_scene_info(job_id: str):
    """シーン情報"""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    job = jobs[job_id]
    result_dir = RESULTS_DIR / job_id
    
    available_files = {}
    for filename in ["point_cloud.ply", "mesh.ply", "rfid_positions.json"]:
        path = result_dir / filename
        available_files[filename] = path.exists()
    
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "mode": job.get("mode"),
        "available_files": available_files,
        "result": job.get("result", {})
    }

# ============================================================
# 処理パイプライン
# ============================================================

async def process_session(job_id: str, session_dir: Path):
    """セッションを処理"""
    try:
        jobs[job_id]["status"] = "processing"
        result_dir = RESULTS_DIR / job_id
        result_dir.mkdir(parents=True, exist_ok=True)
        
        mode = jobs[job_id].get("mode", "rgbd")
        
        # ステップ1: データ解析
        update_job(job_id, 5, "parsing", "Parsing session data...")
        
        parser = ARCoreDataParser(session_dir)
        if not parser.parse():
            raise ValueError("Failed to parse session data")
        
        print(f"[{job_id}] Frames: {len(parser.frames)}, Has depth: {parser.has_depth_data()}")
        
        # ステップ2: 3D再構成
        pcd = None
        mesh = None
        
        if mode == "rgbd" and parser.has_depth_data():
            # RGB-D Integration
            update_job(job_id, 10, "rgbd_integration", "RGB-D integration...")
            
            integration = RGBDIntegration(PROCESSING_CONFIG)
            
            def progress_cb(p, m):
                overall = 10 + int(p * 0.5)
                update_job(job_id, overall, "rgbd_integration", m)
            
            if integration.process_session(parser, progress_cb):
                update_job(job_id, 65, "extracting", "Extracting mesh...")
                pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG)
                
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
        if pcd is not None and mesh is None and len(pcd.points) > 100:
            update_job(job_id, 70, "mesh_generation", "Generating mesh...")
            
            mesh_gen = MeshGenerator(CONFIG.get('mesh', {}))
            mesh = mesh_gen.generate(pcd)
        
        # ステップ4: 結果保存
        update_job(job_id, 85, "saving", "Saving results...")
        
        if pcd is not None:
            pcd_path = result_dir / "point_cloud.ply"
            o3d.io.write_point_cloud(str(pcd_path), pcd)
            print(f"[{job_id}] Saved point cloud: {len(pcd.points)} points")
        
        if mesh is not None:
            mesh_path = result_dir / "mesh.ply"
            o3d.io.write_triangle_mesh(str(mesh_path), mesh)
            mesh_info = MeshGenerator.get_mesh_info(mesh)
            print(f"[{job_id}] Saved mesh: {mesh_info['vertices']} vertices, {mesh_info['triangles']} triangles")
        
        # RFID位置を保存
        export_rfid_positions(parser, result_dir)
        
        # 完了
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["current_step"] = "done"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        jobs[job_id]["result"] = {
            "point_cloud_url": f"/scenes/{job_id}/point_cloud.ply",
            "mesh_url": f"/scenes/{job_id}/mesh.ply" if mesh else None,
            "rfid_positions_url": f"/scenes/{job_id}/rfid_positions.json",
            "viewer_url": f"/viewer/{job_id}",
            "point_count": len(pcd.points) if pcd else 0,
            "mesh_info": MeshGenerator.get_mesh_info(mesh) if mesh else None
        }
        print(f"[{job_id}] ✅ Job completed")
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        print(f"[{job_id}] ❌ Error: {e}")
        import traceback
        traceback.print_exc()


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
    
    uvicorn.run(app, host=host, port=port)

