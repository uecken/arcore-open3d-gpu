#!/usr/bin/env python3
"""
既存のジョブデータをMVS（COLMAP）パイプラインで再処理するスクリプト
"""

import sys
import yaml
import asyncio
from pathlib import Path
from typing import Dict, Any

# main.pyと同じ処理パイプラインを使用
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline
from main import (
    load_config, CONFIG,
    PROCESSING_CONFIG, GPU_CONFIG, DEPTH_ESTIMATION_CONFIG,
    RESULTS_DIR
)

def reprocess_job_mvs(job_id: str):
    """既存のジョブをMVSパイプラインで再処理"""
    session_dir = Path(f"/opt/arcore-open3d-gpu/data/sessions/{job_id}")
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        return False
    
    result_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Reprocessing job with MVS (COLMAP) pipeline: {job_id}")
    print(f"Session dir: {session_dir}")
    print(f"Results dir: {result_dir}")
    print(f"=" * 60)
    print("")
    
    # データ解析
    print("Step 1: Parsing session data...")
    parser = ARCoreDataParser(session_dir)
    if not parser.parse():
        print("Error: Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    if parser.intrinsics:
        print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    print("")
    
    # MVS（COLMAP）パイプライン
    print("Step 2: MVS (COLMAP) pipeline...")
    print("  This will take several hours for 209 frames...")
    print("")
    
    try:
        mvs_pipeline = COLMAPMVSPipeline(CONFIG, GPU_CONFIG)
        
        def progress_cb(p, m):
            print(f"  Progress: {p}% - {m}")
        
        pcd, mesh = mvs_pipeline.process_session(
            parser,
            session_dir,
            result_dir,
            progress_cb
        )
        
        if pcd is None or len(pcd.points) == 0:
            print("✗ Error: MVS point cloud is empty!")
            return False
        
        if mesh is None or len(mesh.triangles) == 0:
            print("✗ Error: MVS mesh is empty!")
            return False
        
        print(f"✓ MVS point cloud: {len(pcd.points)} points")
        print(f"✓ MVS mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
        print("")
        
        # メッシュの品質向上（軽量版）
        print("Step 3: Improving mesh quality...")
        try:
            mesh.remove_duplicated_triangles()
            mesh.remove_duplicated_vertices()
            mesh.remove_non_manifold_edges()
            mesh.remove_unreferenced_vertices()
            print("✓ Mesh cleaned")
        except Exception as e:
            print(f"⚠ Warning: Mesh cleaning failed: {e}")
        
        print("")
        
        # 結果を保存
        print("Step 4: Saving results...")
        
        # 点群を保存
        import open3d as o3d
        pcd_path = result_dir / "point_cloud.ply"
        o3d.io.write_point_cloud(str(pcd_path), pcd, write_ascii=False)
        print(f"✓ Saved point cloud: {pcd_path} ({len(pcd.points)} points)")
        
        # メッシュを保存（簡略化設定を適用）
        output_config = CONFIG.get('output', {})
        mesh_output_config = output_config.get('mesh', {})
        simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)
        max_triangles = mesh_output_config.get('max_triangles_for_viewer', 500000)
        
        original_triangles = len(mesh.triangles)
        mesh_to_save = mesh
        
        # オリジナルメッシュを保存
        original_mesh_path = result_dir / "mesh_original.ply"
        o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=True)
        print(f"✓ Saved original mesh: {original_mesh_path} ({len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles)")
        
        # ビューアー用に簡略化（必要な場合）
        if simplify_for_viewer and original_triangles > max_triangles:
            print(f"  Simplifying mesh for viewer ({original_triangles} → {max_triangles} triangles)...")
            try:
                mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified mesh: {len(mesh_simplified.vertices)} vertices, {len(mesh_simplified.triangles)} triangles")
            except Exception as e:
                print(f"⚠ Warning: Mesh simplification failed: {e}")
                print("  Using original mesh")
        
        # ビューアー用メッシュを保存（ASCII形式）
        mesh_path = result_dir / "mesh.ply"
        o3d.io.write_triangle_mesh(str(mesh_path), mesh_to_save, write_ascii=True)
        print(f"✓ Saved mesh: {mesh_path} ({len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles)")
        
        print("")
        print("=" * 60)
        print("✓ Job reprocessing completed successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"✗ Error during MVS processing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reprocess_job_mvs.py <job_id>")
        sys.exit(1)
    
    job_id = sys.argv[1]
    success = reprocess_job_mvs(job_id)
    sys.exit(0 if success else 1)

