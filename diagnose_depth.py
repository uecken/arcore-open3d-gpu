#!/usr/bin/env python3
"""
Depthデータの診断スクリプト
波打ったカーテン状のメッシュ問題の原因を特定するために、Depthデータの品質を詳細に確認します。
"""

import sys
import numpy as np
import cv2
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
import argparse

# Open3Dをインポート（エラー時は警告のみ）
try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False
    print("⚠ Warning: Open3D not available. Some checks will be skipped.")

from utils.arcore_parser import ARCoreDataParser


def check_depth_file(depth_path: Path, depth_scale: float = 1000.0) -> Dict:
    """Depthファイルの品質をチェック"""
    result = {
        "exists": False,
        "readable": False,
        "format": None,
        "width": None,
        "height": None,
        "dtype": None,
        "min": None,
        "max": None,
        "mean": None,
        "std": None,
        "valid_pixels": 0,
        "zero_pixels": 0,
        "nan_pixels": 0,
        "inf_pixels": 0,
        "valid_ratio": 0.0,
        "depth_range_m": None,  # メートル単位の深度範囲
        "issues": []
    }
    
    if not depth_path.exists():
        result["issues"].append("File does not exist")
        return result
    
    result["exists"] = True
    
    # .raw形式か通常の画像形式かを判定
    is_raw = depth_path.suffix == '.raw'
    
    try:
        if is_raw:
            # ARCoreの.raw形式を読み込み
            depth_data = np.fromfile(str(depth_path), dtype=np.uint16)
            
            # メタデータからサイズを取得（試行錯誤で推測するか、別ファイルから取得）
            # 一般的なサイズ: 640x480, 1280x720 など
            possible_sizes = [
                (640, 480),
                (1280, 720),
                (320, 240),
                (256, 192)
            ]
            
            depth_image = None
            for w, h in possible_sizes:
                if len(depth_data) == w * h:
                    depth_image = depth_data.reshape(h, w)
                    result["width"] = w
                    result["height"] = h
                    break
            
            if depth_image is None:
                result["issues"].append(f"Unknown raw format. Data size: {len(depth_data)} pixels")
                return result
        else:
            # 通常の画像形式（PNG, JPGなど）
            depth_image = cv2.imread(str(depth_path), cv2.IMREAD_ANYDEPTH)
            if depth_image is None:
                result["issues"].append("Failed to read image file")
                return result
            
            result["width"] = depth_image.shape[1]
            result["height"] = depth_image.shape[0]
        
        result["readable"] = True
        result["dtype"] = str(depth_image.dtype)
        
        # 深度値をメートル単位に変換（必要に応じて）
        if depth_image.dtype == np.uint16:
            depth_m = depth_image.astype(np.float32) / depth_scale
        elif depth_image.dtype == np.float32 or depth_image.dtype == np.float64:
            depth_m = depth_image.astype(np.float32)
        else:
            depth_m = depth_image.astype(np.float32)
        
        # 統計情報
        valid_mask = (depth_m > 0) & np.isfinite(depth_m)
        result["valid_pixels"] = int(np.sum(valid_mask))
        result["zero_pixels"] = int(np.sum(depth_m == 0))
        result["nan_pixels"] = int(np.sum(np.isnan(depth_m)))
        result["inf_pixels"] = int(np.sum(np.isinf(depth_m)))
        result["valid_ratio"] = float(result["valid_pixels"] / depth_m.size) if depth_m.size > 0 else 0.0
        
        if result["valid_pixels"] > 0:
            valid_depths = depth_m[valid_mask]
            result["min"] = float(np.min(valid_depths))
            result["max"] = float(np.max(valid_depths))
            result["mean"] = float(np.mean(valid_depths))
            result["std"] = float(np.std(valid_depths))
            result["depth_range_m"] = (result["min"], result["max"])
        else:
            result["issues"].append("No valid depth pixels found")
        
        # 問題チェック
        if result["valid_ratio"] < 0.1:
            result["issues"].append(f"Very few valid pixels ({result['valid_ratio']*100:.1f}%)")
        elif result["valid_ratio"] < 0.5:
            result["issues"].append(f"Low valid pixel ratio ({result['valid_ratio']*100:.1f}%)")
        
        if result["std"] is not None and result["std"] > 2.0:
            result["issues"].append(f"High depth variance (std={result['std']:.2f}m, possibly noisy)")
        
        if result["max"] is not None and result["max"] > 10.0:
            result["issues"].append(f"Very large depth values (max={result['max']:.2f}m)")
        
        if result["nan_pixels"] > 0:
            result["issues"].append(f"Contains NaN values ({result['nan_pixels']} pixels)")
        
        if result["inf_pixels"] > 0:
            result["issues"].append(f"Contains Inf values ({result['inf_pixels']} pixels)")
        
    except Exception as e:
        result["issues"].append(f"Error reading file: {str(e)}")
        result["readable"] = False
    
    return result


def diagnose_job(job_id: str, data_dir: Path = Path("/opt/arcore-open3d-gpu/data")) -> Dict:
    """指定されたジョブのDepthデータを診断"""
    session_dir = data_dir / "sessions" / job_id
    
    if not session_dir.exists():
        return {
            "error": f"Session directory not found: {session_dir}",
            "job_id": job_id
        }
    
    print(f"🔍 Diagnosing job: {job_id}")
    print(f"   Session dir: {session_dir}")
    print()
    
    # パーサーでデータを読み込み
    parser = ARCoreDataParser(session_dir)
    if not parser.parse():
        return {
            "error": "Failed to parse session data",
            "job_id": job_id
        }
    
    # 基本情報
    total_frames = len(parser.frames)
    frames_with_pose = len(parser.get_frames_with_pose())
    frames_with_depth = len(parser.get_frames_with_depth())
    
    print(f"📊 Frame Statistics:")
    print(f"   Total frames: {total_frames}")
    print(f"   Frames with pose: {frames_with_pose}")
    print(f"   Frames with depth: {frames_with_depth}")
    print()
    
    # Depthデータの有無
    has_depth = parser.has_depth_data()
    print(f"✓ Depth data available: {has_depth}")
    
    if not has_depth:
        print()
        print("❌ CRITICAL: No depth data found!")
        print("   → This is the PRIMARY issue. Without depth data, TSDF integration cannot produce clean meshes.")
        print("   → Solutions:")
        print("      1. Enable depth estimation in config.yaml (depth_estimation.force_use: true)")
        print("      2. Switch to COLMAP/Meshroom pipeline")
        print("      3. Use 3DGS/NeRF for mesh-free reconstruction")
        return {
            "job_id": job_id,
            "has_depth": False,
            "total_frames": total_frames,
            "frames_with_depth": 0,
            "recommendation": "NO_DEPTH_DATA"
        }
    
    # Depthファイルの詳細チェック（最初の数フレームをサンプル）
    print()
    print(f"🔬 Analyzing depth files (sampling first 10 frames)...")
    
    sample_frames = [f for f in parser.get_frames_with_depth()][:10]
    depth_checks = []
    
    depth_scale = 1000.0  # デフォルト
    
    for i, frame in enumerate(sample_frames):
        if frame.depth_path is None:
            continue
        
        print(f"\n   Frame {i+1}/{len(sample_frames)}: {frame.depth_path.name}")
        check_result = check_depth_file(frame.depth_path, depth_scale)
        depth_checks.append(check_result)
        
        if check_result["readable"]:
            print(f"      Size: {check_result['width']}x{check_result['height']}")
            print(f"      Valid pixels: {check_result['valid_ratio']*100:.1f}%")
            if check_result["depth_range_m"]:
                print(f"      Depth range: {check_result['depth_range_m'][0]:.2f}m - {check_result['depth_range_m'][1]:.2f}m")
            if check_result["std"] is not None:
                print(f"      Std dev: {check_result['std']:.3f}m")
            if check_result["issues"]:
                print(f"      ⚠ Issues: {', '.join(check_result['issues'])}")
        else:
            print(f"      ❌ Failed to read")
            if check_result["issues"]:
                print(f"         {', '.join(check_result['issues'])}")
    
    # 統計サマリー
    print()
    print("📈 Depth Quality Summary:")
    
    valid_ratios = [c["valid_ratio"] for c in depth_checks if c["readable"]]
    if valid_ratios:
        avg_valid_ratio = np.mean(valid_ratios)
        print(f"   Average valid pixel ratio: {avg_valid_ratio*100:.1f}%")
        
        if avg_valid_ratio < 0.5:
            print(f"   ⚠ Low valid pixel ratio - depth data may be incomplete")
    
    depth_ranges = [c["depth_range_m"] for c in depth_checks if c["readable"] and c["depth_range_m"]]
    if depth_ranges:
        min_depths = [r[0] for r in depth_ranges]
        max_depths = [r[1] for r in depth_ranges]
        print(f"   Depth range: {np.min(min_depths):.2f}m - {np.max(max_depths):.2f}m")
        
        if np.max(max_depths) > 10.0:
            print(f"   ⚠ Very large depth values detected - may indicate noise")
    
    std_devs = [c["std"] for c in depth_checks if c["readable"] and c["std"] is not None]
    if std_devs:
        avg_std = np.mean(std_devs)
        print(f"   Average std dev: {avg_std:.3f}m")
        
        if avg_std > 2.0:
            print(f"   ⚠ High variance - depth data is likely noisy (ARCore estimated depth)")
    
    # 推奨事項
    print()
    print("💡 Recommendations:")
    
    # 深度品質に基づく推奨
    if std_devs and np.mean(std_devs) > 1.5:
        print("   1. ⚠ DEPTH IS NOISY (ARCore estimated depth detected)")
        print("      → Apply depth preprocessing (bilateral filter, inpainting)")
        print("      → Use coarser TSDF parameters (voxel_length: 0.03-0.06m)")
        print("      → Reduce depth_trunc (2.5-4.0m)")
        print("      → Downsample frames (process 1-2 fps instead of 30fps)")
    
    if valid_ratios and np.mean(valid_ratios) < 0.7:
        print("   2. ⚠ MANY MISSING DEPTH PIXELS")
        print("      → Apply depth inpainting to fill holes")
        print("      → Check if depth confidence data is available")
    
    if frames_with_depth < frames_with_pose * 0.8:
        print("   3. ⚠ INCONSISTENT DEPTH AVAILABILITY")
        print(f"      → Only {frames_with_depth}/{frames_with_pose} frames have depth")
        print("      → Consider using depth estimation to fill gaps")
    
    # 常に表示する推奨
    print()
    print("   4. 🔧 TSDF Parameter Adjustments (for noisy depth):")
    print("      → Increase voxel_length: 0.01 → 0.03-0.06m")
    print("      → Reduce depth_trunc: 3.0 → 2.5-4.0m")
    print("      → Enable depth filtering in config.yaml")
    print()
    print("   5. 📐 Frame Sampling:")
    print("      → Process 1-2 fps instead of all frames")
    print("      → Skip similar consecutive frames")
    
    return {
        "job_id": job_id,
        "has_depth": has_depth,
        "total_frames": total_frames,
        "frames_with_pose": frames_with_pose,
        "frames_with_depth": frames_with_depth,
        "depth_checks": depth_checks[:5],  # 最初の5つだけ保存
        "avg_valid_ratio": float(np.mean(valid_ratios)) if valid_ratios else None,
        "avg_std_dev": float(np.mean(std_devs)) if std_devs else None,
        "recommendation": "ADJUST_TSDF_AND_PREPROCESS" if (std_devs and np.mean(std_devs) > 1.5) else "OK"
    }


def main():
    parser = argparse.ArgumentParser(description="Diagnose depth data quality for a job")
    parser.add_argument("job_id", help="Job ID to diagnose")
    parser.add_argument("--data-dir", type=Path, default=Path("/opt/arcore-open3d-gpu/data"),
                       help="Data directory path")
    parser.add_argument("--output", type=Path, help="Output JSON file for results")
    
    args = parser.parse_args()
    
    result = diagnose_job(args.job_id, args.data_dir)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n✓ Results saved to: {args.output}")
    
    # エラーコード
    if "error" in result:
        sys.exit(1)
    if not result.get("has_depth", False):
        sys.exit(2)  # No depth data
    if result.get("recommendation") == "ADJUST_TSDF_AND_PREPROCESS":
        sys.exit(0)  # Depth exists but noisy


if __name__ == "__main__":
    main()

