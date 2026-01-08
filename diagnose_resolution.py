#!/usr/bin/env python3
"""
解像度診断スクリプト
画像解像度と深度解像度を確認し、部屋が認識できない問題の原因を特定します。
"""

import sys
import numpy as np
import cv2
import struct
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
import argparse

from utils.arcore_parser import ARCoreDataParser


def check_image_resolution(image_path: Path) -> Dict:
    """画像ファイルの解像度をチェック"""
    result = {
        "exists": False,
        "readable": False,
        "width": None,
        "height": None,
        "channels": None,
        "file_size_mb": None,
        "format": None
    }
    
    if not image_path.exists():
        return result
    
    result["exists"] = True
    result["file_size_mb"] = image_path.stat().st_size / (1024 * 1024)
    
    try:
        # OpenCVで読み込み
        img = cv2.imread(str(image_path))
        if img is not None:
            result["readable"] = True
            result["height"], result["width"] = img.shape[:2]
            result["channels"] = img.shape[2] if len(img.shape) > 2 else 1
            result["format"] = image_path.suffix.lower()
        else:
            result["readable"] = False
    except Exception as e:
        result["readable"] = False
    
    return result


def check_depth_resolution(depth_path: Path) -> Dict:
    """深度ファイルの解像度をチェック"""
    result = {
        "exists": False,
        "readable": False,
        "width": None,
        "height": None,
        "total_pixels": None,
        "file_size_mb": None,
        "format": None
    }
    
    if not depth_path.exists():
        return result
    
    result["exists"] = True
    result["file_size_mb"] = depth_path.stat().st_size / (1024 * 1024)
    result["format"] = depth_path.suffix.lower()
    
    try:
        if depth_path.suffix == '.raw':
            # ARCoreの.raw形式
            with open(depth_path, 'rb') as f:
                width_bytes = f.read(4)
                height_bytes = f.read(4)
                if len(width_bytes) == 4 and len(height_bytes) == 4:
                    width = struct.unpack('>i', width_bytes)[0]
                    height = struct.unpack('>i', height_bytes)[0]
                    result["readable"] = True
                    result["width"] = width
                    result["height"] = height
                    result["total_pixels"] = width * height
        else:
            # PNGなどの画像形式
            depth = cv2.imread(str(depth_path), cv2.IMREAD_ANYDEPTH)
            if depth is not None:
                result["readable"] = True
                result["height"], result["width"] = depth.shape[:2]
                result["total_pixels"] = depth.shape[0] * depth.shape[1]
    except Exception as e:
        result["readable"] = False
    
    return result


def diagnose_job(job_id: str, data_dir: Path = Path("/opt/arcore-open3d-gpu/data")) -> Dict:
    """指定されたジョブの解像度を診断"""
    session_dir = data_dir / "sessions" / job_id
    
    if not session_dir.exists():
        return {
            "error": f"Session directory not found: {session_dir}",
            "job_id": job_id
        }
    
    print(f"🔍 Diagnosing resolutions for job: {job_id}")
    print(f"   Session dir: {session_dir}")
    print()
    
    # パーサーでデータを読み込み
    parser = ARCoreDataParser(session_dir)
    if not parser.parse():
        return {
            "error": "Failed to parse session data",
            "job_id": job_id
        }
    
    total_frames = len(parser.frames)
    frames_with_images = [f for f in parser.frames if f.image_path is not None]
    frames_with_depth = [f for f in parser.frames if f.depth_path is not None]
    
    print(f"📊 Frame Statistics:")
    print(f"   Total frames: {total_frames}")
    print(f"   Frames with images: {len(frames_with_images)}")
    print(f"   Frames with depth: {len(frames_with_depth)}")
    print()
    
    # 画像解像度を確認（最初の10フレームをサンプル）
    print(f"🖼️  Analyzing image resolutions (sampling first 10 frames)...")
    image_resolutions = []
    
    for i, frame in enumerate(frames_with_images[:10]):
        if frame.image_path is None:
            continue
        
        print(f"\n   Frame {i+1}/{min(10, len(frames_with_images))}: {frame.image_path.name}")
        img_check = check_image_resolution(frame.image_path)
        
        if img_check["readable"]:
            print(f"      Resolution: {img_check['width']}x{img_check['height']}")
            print(f"      Channels: {img_check['channels']}")
            print(f"      File size: {img_check['file_size_mb']:.2f}MB")
            print(f"      Format: {img_check['format']}")
            image_resolutions.append((img_check['width'], img_check['height']))
        else:
            print(f"      ❌ Failed to read")
    
    # 深度解像度を確認（最初の10フレームをサンプル）
    print(f"\n📏 Analyzing depth resolutions (sampling first 10 frames)...")
    depth_resolutions = []
    
    for i, frame in enumerate(frames_with_depth[:10]):
        if frame.depth_path is None:
            continue
        
        print(f"\n   Frame {i+1}/{min(10, len(frames_with_depth))}: {frame.depth_path.name}")
        depth_check = check_depth_resolution(frame.depth_path)
        
        if depth_check["readable"]:
            print(f"      Resolution: {depth_check['width']}x{depth_check['height']}")
            print(f"      Total pixels: {depth_check['total_pixels']:,}")
            print(f"      File size: {depth_check['file_size_mb']:.2f}MB")
            print(f"      Format: {depth_check['format']}")
            depth_resolutions.append((depth_check['width'], depth_check['height']))
        else:
            print(f"      ❌ Failed to read")
    
    # 統計サマリー
    print()
    print("📈 Resolution Summary:")
    
    if image_resolutions:
        unique_img_res = list(set(image_resolutions))
        print(f"   Image resolutions: {unique_img_res}")
        avg_img_res = (np.mean([r[0] for r in image_resolutions]), np.mean([r[1] for r in image_resolutions]))
        print(f"   Average image resolution: {int(avg_img_res[0])}x{int(avg_img_res[1])}")
        
        # 解像度の評価
        if avg_img_res[0] < 1280:
            print(f"   ⚠ Image resolution is low (< 1280px width)")
        elif avg_img_res[0] < 1920:
            print(f"   ⚠ Image resolution is moderate (< 1920px width, Full HD未満)")
        else:
            print(f"   ✓ Image resolution is good (≥ 1920px width, Full HD以上)")
    
    if depth_resolutions:
        unique_depth_res = list(set(depth_resolutions))
        print(f"   Depth resolutions: {unique_depth_res}")
        avg_depth_res = (np.mean([r[0] for r in depth_resolutions]), np.mean([r[1] for r in depth_resolutions]))
        print(f"   Average depth resolution: {int(avg_depth_res[0])}x{int(avg_depth_res[1])}")
        
        # 解像度の評価
        depth_total_pixels = avg_depth_res[0] * avg_depth_res[1]
        if depth_total_pixels < 50000:
            print(f"   ❌ Depth resolution is VERY LOW (< 50k pixels, 部屋が認識できない主因)")
        elif depth_total_pixels < 100000:
            print(f"   ⚠ Depth resolution is low (< 100k pixels, 部屋認識が困難)")
        elif depth_total_pixels < 200000:
            print(f"   ⚠ Depth resolution is moderate (< 200k pixels, 改善の余地あり)")
        else:
            print(f"   ✓ Depth resolution is good (≥ 200k pixels)")
    
    # 解像度比を確認
    if image_resolutions and depth_resolutions:
        avg_img_pixels = avg_img_res[0] * avg_img_res[1]
        avg_depth_pixels = avg_depth_res[0] * avg_depth_res[1]
        ratio = avg_depth_pixels / avg_img_pixels
        
        print()
        print(f"📊 Resolution Ratio:")
        print(f"   Image: {int(avg_img_res[0])}x{int(avg_img_res[1])} = {int(avg_img_pixels):,} pixels")
        print(f"   Depth: {int(avg_depth_res[0])}x{int(avg_depth_res[1])} = {int(avg_depth_pixels):,} pixels")
        print(f"   Depth/Image ratio: {ratio*100:.1f}%")
        
        if ratio < 0.1:
            print(f"   ❌ Depth resolution is VERY LOW compared to image ({ratio*100:.1f}%)")
        elif ratio < 0.3:
            print(f"   ⚠ Depth resolution is LOW compared to image ({ratio*100:.1f}%)")
        else:
            print(f"   ✓ Depth resolution ratio is reasonable ({ratio*100:.1f}%)")
    
    # 推奨事項
    print()
    print("💡 Recommendations:")
    
    if depth_resolutions:
        avg_depth_pixels = avg_depth_res[0] * avg_depth_res[1]
        
        if avg_depth_pixels < 100000:
            print("   1. 🔴 CRITICAL: Depth resolution is too low for room recognition")
            print("      → Increase depth resolution to at least 320x240 (76,800 pixels)")
            print("      → Android app: Use Raw Depth API or configure higher resolution")
            print("      → See ANDROID_DEPTH_RESOLUTION_GUIDE.md for details")
        
        if image_resolutions and avg_img_res[0] < 1920:
            print("   2. ⚠️ Image resolution can be improved")
            print("      → Use Full HD (1920x1080) or higher if possible")
            print("      → Android app: Configure camera resolution settings")
        
        if depth_resolutions and image_resolutions:
            ratio = avg_depth_pixels / (avg_img_res[0] * avg_img_res[1])
            if ratio < 0.2:
                print("   3. ⚠️ Depth resolution is much lower than image resolution")
                print(f"      → Current ratio: {ratio*100:.1f}%")
                print("      → Ideal ratio: 20-50% for room scanning")
                print("      → Increase depth resolution to improve mesh quality")
    
    print()
    print("   4. 🔧 Server-side improvements (immediate):")
    print("      → Reduce voxel_length: 0.03 → 0.02m (if memory allows)")
    print("      → Increase subdivision iterations: 1 → 2 (if memory allows)")
    print("      → Strengthen smoothing: iterations 8 → 10")
    
    return {
        "job_id": job_id,
        "total_frames": total_frames,
        "frames_with_images": len(frames_with_images),
        "frames_with_depth": len(frames_with_depth),
        "image_resolutions": unique_img_res if image_resolutions else [],
        "depth_resolutions": unique_depth_res if depth_resolutions else [],
        "avg_image_resolution": [int(avg_img_res[0]), int(avg_img_res[1])] if image_resolutions else None,
        "avg_depth_resolution": [int(avg_depth_res[0]), int(avg_depth_res[1])] if depth_resolutions else None,
        "depth_image_ratio": float(ratio) if (image_resolutions and depth_resolutions) else None
    }


def main():
    parser = argparse.ArgumentParser(description="Diagnose image and depth resolutions for a job")
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
    
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()

