#!/usr/bin/env python3
"""
ジョブ比較調査スクリプト
2つのジョブを比較して、成功/失敗の原因を分析する

使用方法:
    python scripts/compare_jobs.py <job_id_1> <job_id_2>
    python scripts/compare_jobs.py 7625c1ad 1611626e

出力:
    - 各ジョブの詳細情報
    - 比較表
    - 問題点の特定
"""

import sys
import os
import json
import struct
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_ROOT / "data" / "sessions"
RESULTS_DIR = PROJECT_ROOT / "data" / "results"
JOBS_DB = PROJECT_ROOT / "data" / "jobs_db.json"


@dataclass
class JobAnalysis:
    """ジョブの分析結果"""
    job_id: str
    
    # 基本情報
    status: str = "unknown"
    image_count: int = 0
    has_depth_folder: bool = False
    depth_file_count: int = 0
    
    # 画像解像度・サイズ
    image_width: int = 0
    image_height: int = 0
    image_resolution: str = ""
    avg_image_size_kb: float = 0.0
    total_images_size_mb: float = 0.0
    
    # 深度画像情報
    depth_width: int = 0
    depth_height: int = 0
    depth_resolution: str = ""
    depth_format: str = ""  # raw, png など
    avg_depth_size_kb: float = 0.0
    
    # カメラパラメータ
    camera_fx: float = 0.0
    camera_fy: float = 0.0
    camera_cx: float = 0.0
    camera_cy: float = 0.0
    
    # 撮影間隔分析
    total_duration_sec: float = 0.0
    avg_interval_sec: float = 0.0
    min_interval_sec: float = 0.0
    max_interval_sec: float = 0.0
    gap_count_1sec: int = 0  # 1秒以上のギャップ数
    fps: float = 0.0
    
    # COLMAP sparse reconstruction
    sparse_model_count: int = 0
    largest_model_images: int = 0
    largest_model_points: int = 0
    total_registered_images: int = 0
    
    # COLMAP dense reconstruction
    undistorted_images: int = 0
    depth_map_count: int = 0
    fused_points: int = 0
    
    # 最終結果
    final_point_count: int = 0
    final_mesh_vertices: int = 0
    final_mesh_triangles: int = 0
    depth_source: str = "unknown"
    
    # 問題フラグ
    issues: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []


def get_image_resolution(image_path: Path) -> Tuple[int, int]:
    """画像の解像度を取得（PILを使用）"""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except:
        # PILが使えない場合はfileコマンドを使用
        try:
            result = subprocess.run(
                ['file', str(image_path)],
                capture_output=True, text=True
            )
            # "480x640" のようなパターンを探す
            import re
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
        except:
            pass
    return 0, 0


def analyze_images(images_dir: Path) -> Dict[str, Any]:
    """画像の解像度とサイズを分析"""
    result = {
        "width": 0,
        "height": 0,
        "resolution": "",
        "avg_size_kb": 0.0,
        "total_size_mb": 0.0,
        "count": 0
    }
    
    if not images_dir.exists():
        return result
    
    image_files = [f for f in images_dir.iterdir() 
                   if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
    
    if not image_files:
        return result
    
    result["count"] = len(image_files)
    
    # 最初の画像から解像度を取得
    width, height = get_image_resolution(image_files[0])
    result["width"] = width
    result["height"] = height
    result["resolution"] = f"{width}x{height}" if width > 0 else "unknown"
    
    # ファイルサイズを集計
    total_size = sum(f.stat().st_size for f in image_files)
    result["total_size_mb"] = total_size / (1024 * 1024)
    result["avg_size_kb"] = (total_size / len(image_files)) / 1024
    
    return result


def analyze_depth_files(depth_dir: Path) -> Dict[str, Any]:
    """深度ファイルを分析"""
    result = {
        "count": 0,
        "width": 0,
        "height": 0,
        "resolution": "",
        "format": "",
        "avg_size_kb": 0.0
    }
    
    if not depth_dir.exists():
        return result
    
    depth_files = list(depth_dir.iterdir())
    if not depth_files:
        return result
    
    result["count"] = len(depth_files)
    
    # ファイル形式を判定
    first_file = depth_files[0]
    if first_file.suffix.lower() == '.raw':
        result["format"] = "raw (16-bit)"
        # RAWファイルのサイズから解像度を推定（16bit = 2 bytes per pixel）
        file_size = first_file.stat().st_size
        # 一般的なARCore深度解像度を試す
        common_resolutions = [
            (240, 180),    # 86400 bytes - ARCore標準
            (160, 120),    # 38400 bytes
            (320, 240),    # 153600 bytes
            (256, 192),    # 98304 bytes
            (180, 135),    # 48600 bytes
            (120, 90),     # 21600 bytes
            (80, 60),      # 9600 bytes
            (90, 67),      # 12060 bytes (奇数)
            (90, 68),      # 12240 bytes
            (119, 89),     # 21182 bytes (近似)
            (127, 95),     # 24130 bytes
            (126, 94),     # 23688 bytes
            (113, 85),     # 19210 bytes
            (160, 90),     # 28800 bytes
            (169, 85),     # 28730 bytes (近似)
            (120, 120),    # 28800 bytes
        ]
        for w, h in common_resolutions:
            if file_size == w * h * 2:
                result["width"] = w
                result["height"] = h
                result["resolution"] = f"{w}x{h}"
                break
        if result["width"] == 0:
            # 推定できない場合、近似値を計算
            pixels = file_size // 2
            # 16:9 または 4:3 アスペクト比で推定
            import math
            # 4:3 アスペクト比で推定
            h = int(math.sqrt(pixels * 3 / 4))
            w = int(pixels / h) if h > 0 else 0
            if w > 0 and h > 0:
                result["width"] = w
                result["height"] = h
                result["resolution"] = f"~{w}x{h}"
            else:
                result["resolution"] = f"~{pixels} pixels"
    elif first_file.suffix.lower() == '.png':
        result["format"] = "png"
        w, h = get_image_resolution(first_file)
        result["width"] = w
        result["height"] = h
        result["resolution"] = f"{w}x{h}" if w > 0 else "unknown"
    else:
        result["format"] = first_file.suffix
    
    # 平均ファイルサイズ
    total_size = sum(f.stat().st_size for f in depth_files)
    result["avg_size_kb"] = (total_size / len(depth_files)) / 1024
    
    return result


def load_camera_intrinsics(session_dir: Path) -> Dict[str, float]:
    """camera_intrinsics.jsonを読み込む"""
    result = {"fx": 0.0, "fy": 0.0, "cx": 0.0, "cy": 0.0, "width": 0, "height": 0}
    
    intrinsics_path = session_dir / "camera_intrinsics.json"
    if intrinsics_path.exists():
        try:
            with open(intrinsics_path) as f:
                data = json.load(f)
                result["fx"] = data.get("fx", 0.0)
                result["fy"] = data.get("fy", 0.0)
                result["cx"] = data.get("cx", 0.0)
                result["cy"] = data.get("cy", 0.0)
                result["width"] = data.get("width", 0)
                result["height"] = data.get("height", 0)
        except:
            pass
    
    return result


def analyze_timestamps(images_dir: Path) -> Dict[str, float]:
    """画像のタイムスタンプを分析"""
    result = {
        "count": 0,
        "total_duration_sec": 0.0,
        "avg_interval_sec": 0.0,
        "min_interval_sec": 0.0,
        "max_interval_sec": 0.0,
        "gap_count_1sec": 0,
        "fps": 0.0
    }
    
    if not images_dir.exists():
        return result
    
    # タイムスタンプを抽出（ファイル名: frame_TIMESTAMP.jpg）
    timestamps = []
    for f in sorted(images_dir.iterdir()):
        if f.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            try:
                ts = int(f.stem.replace('frame_', ''))
                timestamps.append(ts)
            except ValueError:
                continue
    
    if len(timestamps) < 2:
        result["count"] = len(timestamps)
        return result
    
    timestamps.sort()
    intervals = [(timestamps[i+1] - timestamps[i]) / 1e9 for i in range(len(timestamps)-1)]
    
    result["count"] = len(timestamps)
    result["total_duration_sec"] = (timestamps[-1] - timestamps[0]) / 1e9
    result["avg_interval_sec"] = sum(intervals) / len(intervals)
    result["min_interval_sec"] = min(intervals)
    result["max_interval_sec"] = max(intervals)
    result["gap_count_1sec"] = sum(1 for i in intervals if i > 1.0)
    result["fps"] = len(timestamps) / result["total_duration_sec"] if result["total_duration_sec"] > 0 else 0
    
    return result


def count_sparse_model_images(images_bin: Path) -> int:
    """images.binから画像数を読み取る"""
    try:
        with open(images_bin, 'rb') as f:
            num = struct.unpack('Q', f.read(8))[0]
            return num
    except:
        return 0


def estimate_points_from_file(points_bin: Path) -> int:
    """points3D.binのファイルサイズから点数を推定"""
    try:
        size = points_bin.stat().st_size
        # 大雑把に1点あたり50バイト程度
        return size // 50
    except:
        return 0


def read_ply_vertex_count(ply_path: Path) -> int:
    """PLYファイルから頂点数を読み取る"""
    try:
        with open(ply_path, 'rb') as f:
            header = b""
            while True:
                line = f.readline()
                header += line
                if b"end_header" in line:
                    break
                if b"element vertex" in line:
                    parts = line.decode('ascii').strip().split()
                    if len(parts) >= 3:
                        return int(parts[2])
        return 0
    except:
        return 0


def analyze_job(job_id: str) -> JobAnalysis:
    """ジョブを分析"""
    analysis = JobAnalysis(job_id=job_id)
    
    session_dir = SESSIONS_DIR / job_id
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        analysis.issues.append("セッションディレクトリが存在しない")
        return analysis
    
    # ジョブステータスを読み込み
    if JOBS_DB.exists():
        try:
            with open(JOBS_DB) as f:
                jobs = json.load(f)
            if job_id in jobs:
                job = jobs[job_id]
                analysis.status = job.get("status", "unknown")
                analysis.image_count = job.get("image_count", 0)
                
                result = job.get("result", {})
                analysis.final_point_count = result.get("point_count", 0)
                analysis.depth_source = result.get("depth_source", "unknown")
                
                mesh_info = result.get("mesh_info", {})
                analysis.final_mesh_vertices = mesh_info.get("vertices", 0)
                analysis.final_mesh_triangles = mesh_info.get("triangles", 0)
        except:
            pass
    
    # カメラパラメータを読み込み
    intrinsics = load_camera_intrinsics(session_dir)
    analysis.camera_fx = intrinsics["fx"]
    analysis.camera_fy = intrinsics["fy"]
    analysis.camera_cx = intrinsics["cx"]
    analysis.camera_cy = intrinsics["cy"]
    
    # 画像の解像度・サイズを分析
    images_dir = session_dir / "images"
    img_analysis = analyze_images(images_dir)
    analysis.image_width = img_analysis["width"]
    analysis.image_height = img_analysis["height"]
    analysis.image_resolution = img_analysis["resolution"]
    analysis.avg_image_size_kb = img_analysis["avg_size_kb"]
    analysis.total_images_size_mb = img_analysis["total_size_mb"]
    
    # 深度フォルダをチェック
    depth_dir = session_dir / "depth"
    if depth_dir.exists():
        analysis.has_depth_folder = True
        depth_analysis = analyze_depth_files(depth_dir)
        analysis.depth_file_count = depth_analysis["count"]
        analysis.depth_width = depth_analysis["width"]
        analysis.depth_height = depth_analysis["height"]
        analysis.depth_resolution = depth_analysis["resolution"]
        analysis.depth_format = depth_analysis["format"]
        analysis.avg_depth_size_kb = depth_analysis["avg_size_kb"]
    else:
        analysis.has_depth_folder = False
        analysis.issues.append("深度フォルダがない（ARCore Depthが無効）")
    
    # 画像のタイムスタンプを分析
    ts_analysis = analyze_timestamps(images_dir)
    analysis.image_count = ts_analysis["count"]
    analysis.total_duration_sec = ts_analysis["total_duration_sec"]
    analysis.avg_interval_sec = ts_analysis["avg_interval_sec"]
    analysis.min_interval_sec = ts_analysis["min_interval_sec"]
    analysis.max_interval_sec = ts_analysis["max_interval_sec"]
    analysis.gap_count_1sec = ts_analysis["gap_count_1sec"]
    analysis.fps = ts_analysis["fps"]
    
    # 撮影頻度の問題チェック
    if analysis.avg_interval_sec > 0.2:
        analysis.issues.append(f"撮影間隔が長い（平均{analysis.avg_interval_sec:.3f}秒）")
    if analysis.gap_count_1sec > 0:
        analysis.issues.append(f"1秒以上のギャップが{analysis.gap_count_1sec}箇所")
    
    # COLMAP sparse reconstruction分析
    sparse_dir = session_dir / "colmap" / "sparse"
    if sparse_dir.exists():
        models = [d for d in sparse_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        analysis.sparse_model_count = len(models)
        
        if analysis.sparse_model_count > 3:
            analysis.issues.append(f"Sparseモデルが{analysis.sparse_model_count}個に分断")
        
        # 各モデルの画像数と点数を集計
        max_images = 0
        max_points = 0
        total_images = 0
        
        for model_dir in models:
            images_bin = model_dir / "images.bin"
            points_bin = model_dir / "points3D.bin"
            
            img_count = count_sparse_model_images(images_bin)
            pts_count = estimate_points_from_file(points_bin)
            
            total_images += img_count
            if img_count > max_images:
                max_images = img_count
                max_points = pts_count
        
        analysis.largest_model_images = max_images
        analysis.largest_model_points = max_points
        analysis.total_registered_images = total_images
        
        # 登録率チェック
        if analysis.image_count > 0:
            register_rate = max_images / analysis.image_count
            if register_rate < 0.7:
                analysis.issues.append(f"画像登録率が低い（{register_rate*100:.0f}%）")
    
    # COLMAP dense reconstruction分析
    dense_dir = session_dir / "colmap" / "dense"
    if dense_dir.exists():
        # undistorted images
        undist_images_dir = dense_dir / "images"
        if undist_images_dir.exists():
            analysis.undistorted_images = len(list(undist_images_dir.iterdir()))
        
        # depth maps
        depth_maps_dir = dense_dir / "stereo" / "depth_maps"
        if depth_maps_dir.exists():
            analysis.depth_map_count = len([f for f in depth_maps_dir.iterdir() if f.suffix == '.bin'])
        
        # fused.ply
        fused_ply = dense_dir / "fused.ply"
        if fused_ply.exists():
            analysis.fused_points = read_ply_vertex_count(fused_ply)
            
            if analysis.fused_points < 10000:
                analysis.issues.append(f"融合点群が少ない（{analysis.fused_points}点）")
    
    return analysis


def print_comparison(job1: JobAnalysis, job2: JobAnalysis):
    """2つのジョブを比較表示"""
    
    def status_icon(val1, val2, higher_is_better=True):
        """比較結果のアイコン"""
        if val1 == val2:
            return "="
        if higher_is_better:
            return "✓" if val1 > val2 else "✗"
        else:
            return "✓" if val1 < val2 else "✗"
    
    print("\n" + "="*80)
    print("ジョブ比較分析レポート")
    print("="*80)
    
    print(f"\n{'項目':<30} | {job1.job_id:<20} | {job2.job_id:<20} | 評価")
    print("-"*80)
    
    # 基本情報
    print(f"{'ステータス':<30} | {job1.status:<20} | {job2.status:<20} |")
    print(f"{'画像数':<30} | {job1.image_count:<20} | {job2.image_count:<20} |")
    
    print()
    print("--- 画像・深度情報 ---")
    print(f"{'画像解像度':<30} | {job1.image_resolution:<20} | {job2.image_resolution:<20} | {'=' if job1.image_resolution == job2.image_resolution else '≠'}")
    print(f"{'平均画像サイズ (KB)':<30} | {job1.avg_image_size_kb:<20.1f} | {job2.avg_image_size_kb:<20.1f} |")
    print(f"{'画像合計サイズ (MB)':<30} | {job1.total_images_size_mb:<20.1f} | {job2.total_images_size_mb:<20.1f} |")
    print(f"{'Depthフォルダ':<30} | {'✓ あり' if job1.has_depth_folder else '✗ なし':<20} | {'✓ あり' if job2.has_depth_folder else '✗ なし':<20} |")
    if job1.has_depth_folder or job2.has_depth_folder:
        print(f"{'Depthファイル数':<30} | {job1.depth_file_count:<20} | {job2.depth_file_count:<20} |")
        d1_res = job1.depth_resolution if job1.depth_resolution else "N/A"
        d2_res = job2.depth_resolution if job2.depth_resolution else "N/A"
        print(f"{'Depth解像度':<30} | {d1_res:<20} | {d2_res:<20} |")
        d1_fmt = job1.depth_format if job1.depth_format else "N/A"
        d2_fmt = job2.depth_format if job2.depth_format else "N/A"
        print(f"{'Depthフォーマット':<30} | {d1_fmt:<20} | {d2_fmt:<20} |")
        print(f"{'平均Depthサイズ (KB)':<30} | {job1.avg_depth_size_kb:<20.1f} | {job2.avg_depth_size_kb:<20.1f} |")
    
    print()
    print("--- カメラパラメータ ---")
    print(f"{'焦点距離 fx':<30} | {job1.camera_fx:<20.2f} | {job2.camera_fx:<20.2f} |")
    print(f"{'焦点距離 fy':<30} | {job1.camera_fy:<20.2f} | {job2.camera_fy:<20.2f} |")
    print(f"{'主点 cx':<30} | {job1.camera_cx:<20.2f} | {job2.camera_cx:<20.2f} |")
    print(f"{'主点 cy':<30} | {job1.camera_cy:<20.2f} | {job2.camera_cy:<20.2f} |")
    
    print()
    print("--- 撮影分析 ---")
    print(f"{'撮影時間 (秒)':<30} | {job1.total_duration_sec:<20.1f} | {job2.total_duration_sec:<20.1f} |")
    print(f"{'平均間隔 (秒)':<30} | {job1.avg_interval_sec:<20.3f} | {job2.avg_interval_sec:<20.3f} | {status_icon(job1.avg_interval_sec, job2.avg_interval_sec, False)}")
    print(f"{'FPS':<30} | {job1.fps:<20.1f} | {job2.fps:<20.1f} | {status_icon(job1.fps, job2.fps)}")
    print(f"{'1秒以上のギャップ':<30} | {job1.gap_count_1sec:<20} | {job2.gap_count_1sec:<20} | {status_icon(job1.gap_count_1sec, job2.gap_count_1sec, False)}")
    
    print()
    print("--- COLMAP Sparse Reconstruction ---")
    print(f"{'Sparseモデル数':<30} | {job1.sparse_model_count:<20} | {job2.sparse_model_count:<20} | {status_icon(job1.sparse_model_count, job2.sparse_model_count, False)}")
    print(f"{'最大モデルの画像数':<30} | {job1.largest_model_images:<20} | {job2.largest_model_images:<20} | {status_icon(job1.largest_model_images, job2.largest_model_images)}")
    print(f"{'最大モデルの3D点数':<30} | {job1.largest_model_points:<20} | {job2.largest_model_points:<20} | {status_icon(job1.largest_model_points, job2.largest_model_points)}")
    
    if job1.image_count > 0 and job2.image_count > 0:
        rate1 = job1.largest_model_images / job1.image_count * 100
        rate2 = job2.largest_model_images / job2.image_count * 100
        print(f"{'画像登録率 (%)':<30} | {rate1:<20.1f} | {rate2:<20.1f} | {status_icon(rate1, rate2)}")
    
    print()
    print("--- COLMAP Dense Reconstruction ---")
    print(f"{'Undistorted画像数':<30} | {job1.undistorted_images:<20} | {job2.undistorted_images:<20} | {status_icon(job1.undistorted_images, job2.undistorted_images)}")
    print(f"{'Depth Map数':<30} | {job1.depth_map_count:<20} | {job2.depth_map_count:<20} | {status_icon(job1.depth_map_count, job2.depth_map_count)}")
    print(f"{'融合点群 (fused.ply)':<30} | {job1.fused_points:<20} | {job2.fused_points:<20} | {status_icon(job1.fused_points, job2.fused_points)}")
    
    print()
    print("--- 最終結果 ---")
    print(f"{'Depth Source':<30} | {job1.depth_source:<20} | {job2.depth_source:<20} |")
    print(f"{'点群点数':<30} | {job1.final_point_count:<20} | {job2.final_point_count:<20} | {status_icon(job1.final_point_count, job2.final_point_count)}")
    print(f"{'メッシュ頂点数':<30} | {job1.final_mesh_vertices:<20} | {job2.final_mesh_vertices:<20} | {status_icon(job1.final_mesh_vertices, job2.final_mesh_vertices)}")
    print(f"{'メッシュ三角形数':<30} | {job1.final_mesh_triangles:<20} | {job2.final_mesh_triangles:<20} | {status_icon(job1.final_mesh_triangles, job2.final_mesh_triangles)}")
    
    # 問題点
    print()
    print("="*80)
    print("検出された問題")
    print("="*80)
    
    print(f"\n{job1.job_id}:")
    if job1.issues:
        for issue in job1.issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ 問題なし")
    
    print(f"\n{job2.job_id}:")
    if job2.issues:
        for issue in job2.issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ 問題なし")
    
    print()


def print_single_analysis(job: JobAnalysis):
    """単一ジョブの詳細分析を表示"""
    print("\n" + "="*60)
    print(f"ジョブ分析レポート: {job.job_id}")
    print("="*60)
    
    print(f"\n{'項目':<35} | {'値':<25}")
    print("-"*60)
    
    print(f"{'ステータス':<35} | {job.status:<25}")
    print(f"{'画像数':<35} | {job.image_count:<25}")
    
    print("\n--- 画像情報 ---")
    print(f"{'画像解像度':<35} | {job.image_resolution:<25}")
    print(f"{'平均画像サイズ':<35} | {job.avg_image_size_kb:.1f} KB")
    print(f"{'画像合計サイズ':<35} | {job.total_images_size_mb:.1f} MB")
    
    print("\n--- 深度情報 ---")
    print(f"{'Depthフォルダ':<35} | {'あり' if job.has_depth_folder else 'なし':<25}")
    if job.has_depth_folder:
        print(f"{'Depthファイル数':<35} | {job.depth_file_count:<25}")
        print(f"{'Depth解像度':<35} | {job.depth_resolution:<25}")
        print(f"{'Depthフォーマット':<35} | {job.depth_format:<25}")
        print(f"{'平均Depthサイズ':<35} | {job.avg_depth_size_kb:.1f} KB")
    
    print("\n--- カメラパラメータ ---")
    print(f"{'焦点距離 (fx, fy)':<35} | ({job.camera_fx:.2f}, {job.camera_fy:.2f})")
    print(f"{'主点 (cx, cy)':<35} | ({job.camera_cx:.2f}, {job.camera_cy:.2f})")
    
    print("\n--- 撮影分析 ---")
    print(f"{'撮影時間':<35} | {job.total_duration_sec:.1f} 秒")
    print(f"{'平均撮影間隔':<35} | {job.avg_interval_sec:.3f} 秒")
    print(f"{'FPS':<35} | {job.fps:.1f}")
    print(f"{'1秒以上のギャップ':<35} | {job.gap_count_1sec} 箇所")
    
    print("\n--- COLMAP Sparse Reconstruction ---")
    print(f"{'Sparseモデル数':<35} | {job.sparse_model_count}")
    print(f"{'最大モデルの画像数':<35} | {job.largest_model_images}")
    print(f"{'最大モデルの3D点数':<35} | {job.largest_model_points}")
    if job.image_count > 0:
        rate = job.largest_model_images / job.image_count * 100
        print(f"{'画像登録率':<35} | {rate:.1f}%")
    
    print("\n--- COLMAP Dense Reconstruction ---")
    print(f"{'Undistorted画像数':<35} | {job.undistorted_images}")
    print(f"{'Depth Map数':<35} | {job.depth_map_count}")
    print(f"{'融合点群 (fused.ply)':<35} | {job.fused_points} 点")
    
    print("\n--- 最終結果 ---")
    print(f"{'Depth Source':<35} | {job.depth_source}")
    print(f"{'点群点数':<35} | {job.final_point_count}")
    print(f"{'メッシュ頂点数':<35} | {job.final_mesh_vertices}")
    print(f"{'メッシュ三角形数':<35} | {job.final_mesh_triangles}")
    
    print("\n" + "="*60)
    print("検出された問題")
    print("="*60)
    if job.issues:
        for issue in job.issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ 問題なし")
    print()


def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  単一ジョブ分析: python scripts/compare_jobs.py <job_id>")
        print("  比較分析:       python scripts/compare_jobs.py <job_id_1> <job_id_2>")
        print()
        print("例:")
        print("  python scripts/compare_jobs.py 7625c1ad")
        print("  python scripts/compare_jobs.py 7625c1ad 1611626e")
        sys.exit(1)
    
    if len(sys.argv) == 2:
        # 単一ジョブ分析
        job_id = sys.argv[1]
        print(f"分析中: {job_id}")
        analysis = analyze_job(job_id)
        print_single_analysis(analysis)
    else:
        # 比較分析
        job_id_1 = sys.argv[1]
        job_id_2 = sys.argv[2]
        print(f"分析中: {job_id_1} vs {job_id_2}")
        analysis1 = analyze_job(job_id_1)
        analysis2 = analyze_job(job_id_2)
        print_comparison(analysis1, analysis2)


if __name__ == "__main__":
    main()


ジョブ比較調査スクリプト
2つのジョブを比較して、成功/失敗の原因を分析する

使用方法:
    python scripts/compare_jobs.py <job_id_1> <job_id_2>
    python scripts/compare_jobs.py 7625c1ad 1611626e

出力:
    - 各ジョブの詳細情報
    - 比較表
    - 問題点の特定
"""

import sys
import os
import json
import struct
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = PROJECT_ROOT / "data" / "sessions"
RESULTS_DIR = PROJECT_ROOT / "data" / "results"
JOBS_DB = PROJECT_ROOT / "data" / "jobs_db.json"


@dataclass
class JobAnalysis:
    """ジョブの分析結果"""
    job_id: str
    
    # 基本情報
    status: str = "unknown"
    image_count: int = 0
    has_depth_folder: bool = False
    depth_file_count: int = 0
    
    # 画像解像度・サイズ
    image_width: int = 0
    image_height: int = 0
    image_resolution: str = ""
    avg_image_size_kb: float = 0.0
    total_images_size_mb: float = 0.0
    
    # 深度画像情報
    depth_width: int = 0
    depth_height: int = 0
    depth_resolution: str = ""
    depth_format: str = ""  # raw, png など
    avg_depth_size_kb: float = 0.0
    
    # カメラパラメータ
    camera_fx: float = 0.0
    camera_fy: float = 0.0
    camera_cx: float = 0.0
    camera_cy: float = 0.0
    
    # 撮影間隔分析
    total_duration_sec: float = 0.0
    avg_interval_sec: float = 0.0
    min_interval_sec: float = 0.0
    max_interval_sec: float = 0.0
    gap_count_1sec: int = 0  # 1秒以上のギャップ数
    fps: float = 0.0
    
    # COLMAP sparse reconstruction
    sparse_model_count: int = 0
    largest_model_images: int = 0
    largest_model_points: int = 0
    total_registered_images: int = 0
    
    # COLMAP dense reconstruction
    undistorted_images: int = 0
    depth_map_count: int = 0
    fused_points: int = 0
    
    # 最終結果
    final_point_count: int = 0
    final_mesh_vertices: int = 0
    final_mesh_triangles: int = 0
    depth_source: str = "unknown"
    
    # 問題フラグ
    issues: List[str] = None
    
    def __post_init__(self):
        if self.issues is None:
            self.issues = []


def get_image_resolution(image_path: Path) -> Tuple[int, int]:
    """画像の解像度を取得（PILを使用）"""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except:
        # PILが使えない場合はfileコマンドを使用
        try:
            result = subprocess.run(
                ['file', str(image_path)],
                capture_output=True, text=True
            )
            # "480x640" のようなパターンを探す
            import re
            match = re.search(r'(\d+)x(\d+)', result.stdout)
            if match:
                return int(match.group(1)), int(match.group(2))
        except:
            pass
    return 0, 0


def analyze_images(images_dir: Path) -> Dict[str, Any]:
    """画像の解像度とサイズを分析"""
    result = {
        "width": 0,
        "height": 0,
        "resolution": "",
        "avg_size_kb": 0.0,
        "total_size_mb": 0.0,
        "count": 0
    }
    
    if not images_dir.exists():
        return result
    
    image_files = [f for f in images_dir.iterdir() 
                   if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
    
    if not image_files:
        return result
    
    result["count"] = len(image_files)
    
    # 最初の画像から解像度を取得
    width, height = get_image_resolution(image_files[0])
    result["width"] = width
    result["height"] = height
    result["resolution"] = f"{width}x{height}" if width > 0 else "unknown"
    
    # ファイルサイズを集計
    total_size = sum(f.stat().st_size for f in image_files)
    result["total_size_mb"] = total_size / (1024 * 1024)
    result["avg_size_kb"] = (total_size / len(image_files)) / 1024
    
    return result


def analyze_depth_files(depth_dir: Path) -> Dict[str, Any]:
    """深度ファイルを分析"""
    result = {
        "count": 0,
        "width": 0,
        "height": 0,
        "resolution": "",
        "format": "",
        "avg_size_kb": 0.0
    }
    
    if not depth_dir.exists():
        return result
    
    depth_files = list(depth_dir.iterdir())
    if not depth_files:
        return result
    
    result["count"] = len(depth_files)
    
    # ファイル形式を判定
    first_file = depth_files[0]
    if first_file.suffix.lower() == '.raw':
        result["format"] = "raw (16-bit)"
        # RAWファイルのサイズから解像度を推定（16bit = 2 bytes per pixel）
        file_size = first_file.stat().st_size
        # 一般的なARCore深度解像度を試す
        common_resolutions = [
            (240, 180),    # 86400 bytes - ARCore標準
            (160, 120),    # 38400 bytes
            (320, 240),    # 153600 bytes
            (256, 192),    # 98304 bytes
            (180, 135),    # 48600 bytes
            (120, 90),     # 21600 bytes
            (80, 60),      # 9600 bytes
            (90, 67),      # 12060 bytes (奇数)
            (90, 68),      # 12240 bytes
            (119, 89),     # 21182 bytes (近似)
            (127, 95),     # 24130 bytes
            (126, 94),     # 23688 bytes
            (113, 85),     # 19210 bytes
            (160, 90),     # 28800 bytes
            (169, 85),     # 28730 bytes (近似)
            (120, 120),    # 28800 bytes
        ]
        for w, h in common_resolutions:
            if file_size == w * h * 2:
                result["width"] = w
                result["height"] = h
                result["resolution"] = f"{w}x{h}"
                break
        if result["width"] == 0:
            # 推定できない場合、近似値を計算
            pixels = file_size // 2
            # 16:9 または 4:3 アスペクト比で推定
            import math
            # 4:3 アスペクト比で推定
            h = int(math.sqrt(pixels * 3 / 4))
            w = int(pixels / h) if h > 0 else 0
            if w > 0 and h > 0:
                result["width"] = w
                result["height"] = h
                result["resolution"] = f"~{w}x{h}"
            else:
                result["resolution"] = f"~{pixels} pixels"
    elif first_file.suffix.lower() == '.png':
        result["format"] = "png"
        w, h = get_image_resolution(first_file)
        result["width"] = w
        result["height"] = h
        result["resolution"] = f"{w}x{h}" if w > 0 else "unknown"
    else:
        result["format"] = first_file.suffix
    
    # 平均ファイルサイズ
    total_size = sum(f.stat().st_size for f in depth_files)
    result["avg_size_kb"] = (total_size / len(depth_files)) / 1024
    
    return result


def load_camera_intrinsics(session_dir: Path) -> Dict[str, float]:
    """camera_intrinsics.jsonを読み込む"""
    result = {"fx": 0.0, "fy": 0.0, "cx": 0.0, "cy": 0.0, "width": 0, "height": 0}
    
    intrinsics_path = session_dir / "camera_intrinsics.json"
    if intrinsics_path.exists():
        try:
            with open(intrinsics_path) as f:
                data = json.load(f)
                result["fx"] = data.get("fx", 0.0)
                result["fy"] = data.get("fy", 0.0)
                result["cx"] = data.get("cx", 0.0)
                result["cy"] = data.get("cy", 0.0)
                result["width"] = data.get("width", 0)
                result["height"] = data.get("height", 0)
        except:
            pass
    
    return result


def analyze_timestamps(images_dir: Path) -> Dict[str, float]:
    """画像のタイムスタンプを分析"""
    result = {
        "count": 0,
        "total_duration_sec": 0.0,
        "avg_interval_sec": 0.0,
        "min_interval_sec": 0.0,
        "max_interval_sec": 0.0,
        "gap_count_1sec": 0,
        "fps": 0.0
    }
    
    if not images_dir.exists():
        return result
    
    # タイムスタンプを抽出（ファイル名: frame_TIMESTAMP.jpg）
    timestamps = []
    for f in sorted(images_dir.iterdir()):
        if f.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            try:
                ts = int(f.stem.replace('frame_', ''))
                timestamps.append(ts)
            except ValueError:
                continue
    
    if len(timestamps) < 2:
        result["count"] = len(timestamps)
        return result
    
    timestamps.sort()
    intervals = [(timestamps[i+1] - timestamps[i]) / 1e9 for i in range(len(timestamps)-1)]
    
    result["count"] = len(timestamps)
    result["total_duration_sec"] = (timestamps[-1] - timestamps[0]) / 1e9
    result["avg_interval_sec"] = sum(intervals) / len(intervals)
    result["min_interval_sec"] = min(intervals)
    result["max_interval_sec"] = max(intervals)
    result["gap_count_1sec"] = sum(1 for i in intervals if i > 1.0)
    result["fps"] = len(timestamps) / result["total_duration_sec"] if result["total_duration_sec"] > 0 else 0
    
    return result


def count_sparse_model_images(images_bin: Path) -> int:
    """images.binから画像数を読み取る"""
    try:
        with open(images_bin, 'rb') as f:
            num = struct.unpack('Q', f.read(8))[0]
            return num
    except:
        return 0


def estimate_points_from_file(points_bin: Path) -> int:
    """points3D.binのファイルサイズから点数を推定"""
    try:
        size = points_bin.stat().st_size
        # 大雑把に1点あたり50バイト程度
        return size // 50
    except:
        return 0


def read_ply_vertex_count(ply_path: Path) -> int:
    """PLYファイルから頂点数を読み取る"""
    try:
        with open(ply_path, 'rb') as f:
            header = b""
            while True:
                line = f.readline()
                header += line
                if b"end_header" in line:
                    break
                if b"element vertex" in line:
                    parts = line.decode('ascii').strip().split()
                    if len(parts) >= 3:
                        return int(parts[2])
        return 0
    except:
        return 0


def analyze_job(job_id: str) -> JobAnalysis:
    """ジョブを分析"""
    analysis = JobAnalysis(job_id=job_id)
    
    session_dir = SESSIONS_DIR / job_id
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        analysis.issues.append("セッションディレクトリが存在しない")
        return analysis
    
    # ジョブステータスを読み込み
    if JOBS_DB.exists():
        try:
            with open(JOBS_DB) as f:
                jobs = json.load(f)
            if job_id in jobs:
                job = jobs[job_id]
                analysis.status = job.get("status", "unknown")
                analysis.image_count = job.get("image_count", 0)
                
                result = job.get("result", {})
                analysis.final_point_count = result.get("point_count", 0)
                analysis.depth_source = result.get("depth_source", "unknown")
                
                mesh_info = result.get("mesh_info", {})
                analysis.final_mesh_vertices = mesh_info.get("vertices", 0)
                analysis.final_mesh_triangles = mesh_info.get("triangles", 0)
        except:
            pass
    
    # カメラパラメータを読み込み
    intrinsics = load_camera_intrinsics(session_dir)
    analysis.camera_fx = intrinsics["fx"]
    analysis.camera_fy = intrinsics["fy"]
    analysis.camera_cx = intrinsics["cx"]
    analysis.camera_cy = intrinsics["cy"]
    
    # 画像の解像度・サイズを分析
    images_dir = session_dir / "images"
    img_analysis = analyze_images(images_dir)
    analysis.image_width = img_analysis["width"]
    analysis.image_height = img_analysis["height"]
    analysis.image_resolution = img_analysis["resolution"]
    analysis.avg_image_size_kb = img_analysis["avg_size_kb"]
    analysis.total_images_size_mb = img_analysis["total_size_mb"]
    
    # 深度フォルダをチェック
    depth_dir = session_dir / "depth"
    if depth_dir.exists():
        analysis.has_depth_folder = True
        depth_analysis = analyze_depth_files(depth_dir)
        analysis.depth_file_count = depth_analysis["count"]
        analysis.depth_width = depth_analysis["width"]
        analysis.depth_height = depth_analysis["height"]
        analysis.depth_resolution = depth_analysis["resolution"]
        analysis.depth_format = depth_analysis["format"]
        analysis.avg_depth_size_kb = depth_analysis["avg_size_kb"]
    else:
        analysis.has_depth_folder = False
        analysis.issues.append("深度フォルダがない（ARCore Depthが無効）")
    
    # 画像のタイムスタンプを分析
    ts_analysis = analyze_timestamps(images_dir)
    analysis.image_count = ts_analysis["count"]
    analysis.total_duration_sec = ts_analysis["total_duration_sec"]
    analysis.avg_interval_sec = ts_analysis["avg_interval_sec"]
    analysis.min_interval_sec = ts_analysis["min_interval_sec"]
    analysis.max_interval_sec = ts_analysis["max_interval_sec"]
    analysis.gap_count_1sec = ts_analysis["gap_count_1sec"]
    analysis.fps = ts_analysis["fps"]
    
    # 撮影頻度の問題チェック
    if analysis.avg_interval_sec > 0.2:
        analysis.issues.append(f"撮影間隔が長い（平均{analysis.avg_interval_sec:.3f}秒）")
    if analysis.gap_count_1sec > 0:
        analysis.issues.append(f"1秒以上のギャップが{analysis.gap_count_1sec}箇所")
    
    # COLMAP sparse reconstruction分析
    sparse_dir = session_dir / "colmap" / "sparse"
    if sparse_dir.exists():
        models = [d for d in sparse_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        analysis.sparse_model_count = len(models)
        
        if analysis.sparse_model_count > 3:
            analysis.issues.append(f"Sparseモデルが{analysis.sparse_model_count}個に分断")
        
        # 各モデルの画像数と点数を集計
        max_images = 0
        max_points = 0
        total_images = 0
        
        for model_dir in models:
            images_bin = model_dir / "images.bin"
            points_bin = model_dir / "points3D.bin"
            
            img_count = count_sparse_model_images(images_bin)
            pts_count = estimate_points_from_file(points_bin)
            
            total_images += img_count
            if img_count > max_images:
                max_images = img_count
                max_points = pts_count
        
        analysis.largest_model_images = max_images
        analysis.largest_model_points = max_points
        analysis.total_registered_images = total_images
        
        # 登録率チェック
        if analysis.image_count > 0:
            register_rate = max_images / analysis.image_count
            if register_rate < 0.7:
                analysis.issues.append(f"画像登録率が低い（{register_rate*100:.0f}%）")
    
    # COLMAP dense reconstruction分析
    dense_dir = session_dir / "colmap" / "dense"
    if dense_dir.exists():
        # undistorted images
        undist_images_dir = dense_dir / "images"
        if undist_images_dir.exists():
            analysis.undistorted_images = len(list(undist_images_dir.iterdir()))
        
        # depth maps
        depth_maps_dir = dense_dir / "stereo" / "depth_maps"
        if depth_maps_dir.exists():
            analysis.depth_map_count = len([f for f in depth_maps_dir.iterdir() if f.suffix == '.bin'])
        
        # fused.ply
        fused_ply = dense_dir / "fused.ply"
        if fused_ply.exists():
            analysis.fused_points = read_ply_vertex_count(fused_ply)
            
            if analysis.fused_points < 10000:
                analysis.issues.append(f"融合点群が少ない（{analysis.fused_points}点）")
    
    return analysis


def print_comparison(job1: JobAnalysis, job2: JobAnalysis):
    """2つのジョブを比較表示"""
    
    def status_icon(val1, val2, higher_is_better=True):
        """比較結果のアイコン"""
        if val1 == val2:
            return "="
        if higher_is_better:
            return "✓" if val1 > val2 else "✗"
        else:
            return "✓" if val1 < val2 else "✗"
    
    print("\n" + "="*80)
    print("ジョブ比較分析レポート")
    print("="*80)
    
    print(f"\n{'項目':<30} | {job1.job_id:<20} | {job2.job_id:<20} | 評価")
    print("-"*80)
    
    # 基本情報
    print(f"{'ステータス':<30} | {job1.status:<20} | {job2.status:<20} |")
    print(f"{'画像数':<30} | {job1.image_count:<20} | {job2.image_count:<20} |")
    
    print()
    print("--- 画像・深度情報 ---")
    print(f"{'画像解像度':<30} | {job1.image_resolution:<20} | {job2.image_resolution:<20} | {'=' if job1.image_resolution == job2.image_resolution else '≠'}")
    print(f"{'平均画像サイズ (KB)':<30} | {job1.avg_image_size_kb:<20.1f} | {job2.avg_image_size_kb:<20.1f} |")
    print(f"{'画像合計サイズ (MB)':<30} | {job1.total_images_size_mb:<20.1f} | {job2.total_images_size_mb:<20.1f} |")
    print(f"{'Depthフォルダ':<30} | {'✓ あり' if job1.has_depth_folder else '✗ なし':<20} | {'✓ あり' if job2.has_depth_folder else '✗ なし':<20} |")
    if job1.has_depth_folder or job2.has_depth_folder:
        print(f"{'Depthファイル数':<30} | {job1.depth_file_count:<20} | {job2.depth_file_count:<20} |")
        d1_res = job1.depth_resolution if job1.depth_resolution else "N/A"
        d2_res = job2.depth_resolution if job2.depth_resolution else "N/A"
        print(f"{'Depth解像度':<30} | {d1_res:<20} | {d2_res:<20} |")
        d1_fmt = job1.depth_format if job1.depth_format else "N/A"
        d2_fmt = job2.depth_format if job2.depth_format else "N/A"
        print(f"{'Depthフォーマット':<30} | {d1_fmt:<20} | {d2_fmt:<20} |")
        print(f"{'平均Depthサイズ (KB)':<30} | {job1.avg_depth_size_kb:<20.1f} | {job2.avg_depth_size_kb:<20.1f} |")
    
    print()
    print("--- カメラパラメータ ---")
    print(f"{'焦点距離 fx':<30} | {job1.camera_fx:<20.2f} | {job2.camera_fx:<20.2f} |")
    print(f"{'焦点距離 fy':<30} | {job1.camera_fy:<20.2f} | {job2.camera_fy:<20.2f} |")
    print(f"{'主点 cx':<30} | {job1.camera_cx:<20.2f} | {job2.camera_cx:<20.2f} |")
    print(f"{'主点 cy':<30} | {job1.camera_cy:<20.2f} | {job2.camera_cy:<20.2f} |")
    
    print()
    print("--- 撮影分析 ---")
    print(f"{'撮影時間 (秒)':<30} | {job1.total_duration_sec:<20.1f} | {job2.total_duration_sec:<20.1f} |")
    print(f"{'平均間隔 (秒)':<30} | {job1.avg_interval_sec:<20.3f} | {job2.avg_interval_sec:<20.3f} | {status_icon(job1.avg_interval_sec, job2.avg_interval_sec, False)}")
    print(f"{'FPS':<30} | {job1.fps:<20.1f} | {job2.fps:<20.1f} | {status_icon(job1.fps, job2.fps)}")
    print(f"{'1秒以上のギャップ':<30} | {job1.gap_count_1sec:<20} | {job2.gap_count_1sec:<20} | {status_icon(job1.gap_count_1sec, job2.gap_count_1sec, False)}")
    
    print()
    print("--- COLMAP Sparse Reconstruction ---")
    print(f"{'Sparseモデル数':<30} | {job1.sparse_model_count:<20} | {job2.sparse_model_count:<20} | {status_icon(job1.sparse_model_count, job2.sparse_model_count, False)}")
    print(f"{'最大モデルの画像数':<30} | {job1.largest_model_images:<20} | {job2.largest_model_images:<20} | {status_icon(job1.largest_model_images, job2.largest_model_images)}")
    print(f"{'最大モデルの3D点数':<30} | {job1.largest_model_points:<20} | {job2.largest_model_points:<20} | {status_icon(job1.largest_model_points, job2.largest_model_points)}")
    
    if job1.image_count > 0 and job2.image_count > 0:
        rate1 = job1.largest_model_images / job1.image_count * 100
        rate2 = job2.largest_model_images / job2.image_count * 100
        print(f"{'画像登録率 (%)':<30} | {rate1:<20.1f} | {rate2:<20.1f} | {status_icon(rate1, rate2)}")
    
    print()
    print("--- COLMAP Dense Reconstruction ---")
    print(f"{'Undistorted画像数':<30} | {job1.undistorted_images:<20} | {job2.undistorted_images:<20} | {status_icon(job1.undistorted_images, job2.undistorted_images)}")
    print(f"{'Depth Map数':<30} | {job1.depth_map_count:<20} | {job2.depth_map_count:<20} | {status_icon(job1.depth_map_count, job2.depth_map_count)}")
    print(f"{'融合点群 (fused.ply)':<30} | {job1.fused_points:<20} | {job2.fused_points:<20} | {status_icon(job1.fused_points, job2.fused_points)}")
    
    print()
    print("--- 最終結果 ---")
    print(f"{'Depth Source':<30} | {job1.depth_source:<20} | {job2.depth_source:<20} |")
    print(f"{'点群点数':<30} | {job1.final_point_count:<20} | {job2.final_point_count:<20} | {status_icon(job1.final_point_count, job2.final_point_count)}")
    print(f"{'メッシュ頂点数':<30} | {job1.final_mesh_vertices:<20} | {job2.final_mesh_vertices:<20} | {status_icon(job1.final_mesh_vertices, job2.final_mesh_vertices)}")
    print(f"{'メッシュ三角形数':<30} | {job1.final_mesh_triangles:<20} | {job2.final_mesh_triangles:<20} | {status_icon(job1.final_mesh_triangles, job2.final_mesh_triangles)}")
    
    # 問題点
    print()
    print("="*80)
    print("検出された問題")
    print("="*80)
    
    print(f"\n{job1.job_id}:")
    if job1.issues:
        for issue in job1.issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ 問題なし")
    
    print(f"\n{job2.job_id}:")
    if job2.issues:
        for issue in job2.issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ 問題なし")
    
    print()


def print_single_analysis(job: JobAnalysis):
    """単一ジョブの詳細分析を表示"""
    print("\n" + "="*60)
    print(f"ジョブ分析レポート: {job.job_id}")
    print("="*60)
    
    print(f"\n{'項目':<35} | {'値':<25}")
    print("-"*60)
    
    print(f"{'ステータス':<35} | {job.status:<25}")
    print(f"{'画像数':<35} | {job.image_count:<25}")
    
    print("\n--- 画像情報 ---")
    print(f"{'画像解像度':<35} | {job.image_resolution:<25}")
    print(f"{'平均画像サイズ':<35} | {job.avg_image_size_kb:.1f} KB")
    print(f"{'画像合計サイズ':<35} | {job.total_images_size_mb:.1f} MB")
    
    print("\n--- 深度情報 ---")
    print(f"{'Depthフォルダ':<35} | {'あり' if job.has_depth_folder else 'なし':<25}")
    if job.has_depth_folder:
        print(f"{'Depthファイル数':<35} | {job.depth_file_count:<25}")
        print(f"{'Depth解像度':<35} | {job.depth_resolution:<25}")
        print(f"{'Depthフォーマット':<35} | {job.depth_format:<25}")
        print(f"{'平均Depthサイズ':<35} | {job.avg_depth_size_kb:.1f} KB")
    
    print("\n--- カメラパラメータ ---")
    print(f"{'焦点距離 (fx, fy)':<35} | ({job.camera_fx:.2f}, {job.camera_fy:.2f})")
    print(f"{'主点 (cx, cy)':<35} | ({job.camera_cx:.2f}, {job.camera_cy:.2f})")
    
    print("\n--- 撮影分析 ---")
    print(f"{'撮影時間':<35} | {job.total_duration_sec:.1f} 秒")
    print(f"{'平均撮影間隔':<35} | {job.avg_interval_sec:.3f} 秒")
    print(f"{'FPS':<35} | {job.fps:.1f}")
    print(f"{'1秒以上のギャップ':<35} | {job.gap_count_1sec} 箇所")
    
    print("\n--- COLMAP Sparse Reconstruction ---")
    print(f"{'Sparseモデル数':<35} | {job.sparse_model_count}")
    print(f"{'最大モデルの画像数':<35} | {job.largest_model_images}")
    print(f"{'最大モデルの3D点数':<35} | {job.largest_model_points}")
    if job.image_count > 0:
        rate = job.largest_model_images / job.image_count * 100
        print(f"{'画像登録率':<35} | {rate:.1f}%")
    
    print("\n--- COLMAP Dense Reconstruction ---")
    print(f"{'Undistorted画像数':<35} | {job.undistorted_images}")
    print(f"{'Depth Map数':<35} | {job.depth_map_count}")
    print(f"{'融合点群 (fused.ply)':<35} | {job.fused_points} 点")
    
    print("\n--- 最終結果 ---")
    print(f"{'Depth Source':<35} | {job.depth_source}")
    print(f"{'点群点数':<35} | {job.final_point_count}")
    print(f"{'メッシュ頂点数':<35} | {job.final_mesh_vertices}")
    print(f"{'メッシュ三角形数':<35} | {job.final_mesh_triangles}")
    
    print("\n" + "="*60)
    print("検出された問題")
    print("="*60)
    if job.issues:
        for issue in job.issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ 問題なし")
    print()


def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  単一ジョブ分析: python scripts/compare_jobs.py <job_id>")
        print("  比較分析:       python scripts/compare_jobs.py <job_id_1> <job_id_2>")
        print()
        print("例:")
        print("  python scripts/compare_jobs.py 7625c1ad")
        print("  python scripts/compare_jobs.py 7625c1ad 1611626e")
        sys.exit(1)
    
    if len(sys.argv) == 2:
        # 単一ジョブ分析
        job_id = sys.argv[1]
        print(f"分析中: {job_id}")
        analysis = analyze_job(job_id)
        print_single_analysis(analysis)
    else:
        # 比較分析
        job_id_1 = sys.argv[1]
        job_id_2 = sys.argv[2]
        print(f"分析中: {job_id_1} vs {job_id_2}")
        analysis1 = analyze_job(job_id_1)
        analysis2 = analyze_job(job_id_2)
        print_comparison(analysis1, analysis2)


if __name__ == "__main__":
    main()
