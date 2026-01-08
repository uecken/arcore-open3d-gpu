#!/usr/bin/env python3
"""
既存のジョブデータを再処理するスクリプト（MiDaS深度推定を使用）
セッションデータからRGB-D統合をやり直し、更新された設定でメッシュを生成
"""

import sys
import yaml
import open3d as o3d
from pathlib import Path
from typing import Dict, Any

# main.pyと同じ処理パイプラインを使用
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser

# GPU対応版を優先的に使用
try:
    from pipeline.rgbd_integration_gpu import RGBDIntegrationGPU as RGBDIntegration
    from pipeline.mesh_generation_gpu import create_mesh_from_rgbd_volume_gpu as create_mesh_from_rgbd_volume
    GPU_AVAILABLE = True
    print("✓ Using GPU-accelerated pipeline")
except ImportError:
    from pipeline.rgbd_integration import RGBDIntegration
    from pipeline.mesh_generation import create_mesh_from_rgbd_volume
    GPU_AVAILABLE = False
    print("⚠ GPU pipeline not available, using CPU pipeline")

# main.pyと同じ処理ロジックを使用
from main import (
    load_config, CONFIG,
    PROCESSING_CONFIG, GPU_CONFIG, DEPTH_ESTIMATION_CONFIG,
    RESULTS_DIR
)

def reprocess_job(job_id: str):
    """既存のジョブを再処理"""
    session_dir = Path(f"/opt/arcore-open3d-gpu/data/sessions/{job_id}")
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        return False
    
    result_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Reprocessing job: {job_id}")
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
    
    print(f"Frames: {len(parser.frames)}, Has depth: {parser.has_depth_data()}")
    print("")
    
    # RGB-D統合（MiDaS深度推定を強制使用）
    print("Step 2: RGB-D integration with MiDaS depth estimation...")
    
    if GPU_AVAILABLE:
        integration = RGBDIntegration(PROCESSING_CONFIG, GPU_CONFIG)
    else:
        integration = RGBDIntegration(PROCESSING_CONFIG)
    
    # 深度推定を強制使用
    force_depth_estimation = DEPTH_ESTIMATION_CONFIG.get('force_use', True)
    
    def progress_cb(p, m):
        print(f"  Progress: {p}% - {m}")
    
    if not integration.process_session(parser, progress_cb, force_depth_estimation=force_depth_estimation):
        print("Error: RGB-D integration failed")
        return False
    
    print("")
    print("Step 3: Extracting point cloud and mesh...")
    
    # 点群とメッシュを抽出
    if GPU_AVAILABLE:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG, GPU_CONFIG)
    else:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG)
    
    if pcd is None or len(pcd.points) == 0:
        print("Error: Failed to extract point cloud")
        return False
    
    if mesh is None or len(mesh.triangles) == 0:
        print("Error: Failed to extract mesh")
        return False
    
    print(f"Extracted point cloud: {len(pcd.points)} points")
    print(f"Extracted mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    print("")
    
    # main.pyと同じ品質向上処理を適用
    print("Step 4: Improving mesh quality...")
    
    # main.pyのprocess_session関数から品質向上処理をインポート
    # ここでは簡略化のため、regenerate_mesh.pyの関数を使用
    from regenerate_mesh import improve_mesh_quality
    
    mesh = improve_mesh_quality(mesh, CONFIG, job_id)
    
    print("")
    print("Step 5: Saving results...")
    
    # 点群を保存
    pcd_path = result_dir / "point_cloud.ply"
    o3d.io.write_point_cloud(str(pcd_path), pcd, write_ascii=False)
    print(f"✓ Saved point cloud: {pcd_path}")
    
    # メッシュを保存（簡略化設定を適用）
    output_config = CONFIG.get('output', {})
    mesh_output_config = output_config.get('mesh', {})
    simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)
    max_triangles = mesh_output_config.get('max_triangles_for_viewer', 500000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    # 簡略化する前に元のメッシュを保存
    if simplify_for_viewer and original_triangles > max_triangles:
        original_mesh_path = result_dir / "mesh_original.ply"
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
            
            mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
            if len(mesh_simplified.triangles) > 0:
                mesh_simplified.remove_duplicated_triangles()
                mesh_simplified.remove_duplicated_vertices()
                mesh_simplified.remove_non_manifold_edges()
                mesh_simplified.compute_vertex_normals()
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified mesh: {len(mesh_simplified.triangles)} triangles")
        except Exception as e:
            print(f"⚠ Simplification failed: {e}, using original mesh")
    
    # メッシュを保存（ASCII形式）
    mesh_path = result_dir / "mesh.ply"
    o3d.io.write_triangle_mesh(
        str(mesh_path),
        mesh_to_save,
        write_ascii=True,
        compressed=False
    )
    print(f"✓ Saved mesh: {mesh_path}")
    print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
    print("")
    
    print("✅ Job reprocessed successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reprocess_job.py <job_id>")
        print("Example: python reprocess_job.py 2151df2e")
        sys.exit(1)
    
    job_id = sys.argv[1]
    success = reprocess_job(job_id)
    sys.exit(0 if success else 1)

既存のジョブデータを再処理するスクリプト（MiDaS深度推定を使用）
セッションデータからRGB-D統合をやり直し、更新された設定でメッシュを生成
"""

import sys
import yaml
import open3d as o3d
from pathlib import Path
from typing import Dict, Any

# main.pyと同じ処理パイプラインを使用
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser

# GPU対応版を優先的に使用
try:
    from pipeline.rgbd_integration_gpu import RGBDIntegrationGPU as RGBDIntegration
    from pipeline.mesh_generation_gpu import create_mesh_from_rgbd_volume_gpu as create_mesh_from_rgbd_volume
    GPU_AVAILABLE = True
    print("✓ Using GPU-accelerated pipeline")
except ImportError:
    from pipeline.rgbd_integration import RGBDIntegration
    from pipeline.mesh_generation import create_mesh_from_rgbd_volume
    GPU_AVAILABLE = False
    print("⚠ GPU pipeline not available, using CPU pipeline")

# main.pyと同じ処理ロジックを使用
from main import (
    load_config, CONFIG,
    PROCESSING_CONFIG, GPU_CONFIG, DEPTH_ESTIMATION_CONFIG,
    RESULTS_DIR
)

def reprocess_job(job_id: str):
    """既存のジョブを再処理"""
    session_dir = Path(f"/opt/arcore-open3d-gpu/data/sessions/{job_id}")
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        return False
    
    result_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Reprocessing job: {job_id}")
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
    
    print(f"Frames: {len(parser.frames)}, Has depth: {parser.has_depth_data()}")
    print("")
    
    # RGB-D統合（MiDaS深度推定を強制使用）
    print("Step 2: RGB-D integration with MiDaS depth estimation...")
    
    if GPU_AVAILABLE:
        integration = RGBDIntegration(PROCESSING_CONFIG, GPU_CONFIG)
    else:
        integration = RGBDIntegration(PROCESSING_CONFIG)
    
    # 深度推定を強制使用
    force_depth_estimation = DEPTH_ESTIMATION_CONFIG.get('force_use', True)
    
    def progress_cb(p, m):
        print(f"  Progress: {p}% - {m}")
    
    if not integration.process_session(parser, progress_cb, force_depth_estimation=force_depth_estimation):
        print("Error: RGB-D integration failed")
        return False
    
    print("")
    print("Step 3: Extracting point cloud and mesh...")
    
    # 点群とメッシュを抽出
    if GPU_AVAILABLE:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG, GPU_CONFIG)
    else:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG)
    
    if pcd is None or len(pcd.points) == 0:
        print("Error: Failed to extract point cloud")
        return False
    
    if mesh is None or len(mesh.triangles) == 0:
        print("Error: Failed to extract mesh")
        return False
    
    print(f"Extracted point cloud: {len(pcd.points)} points")
    print(f"Extracted mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    print("")
    
    # main.pyと同じ品質向上処理を適用
    print("Step 4: Improving mesh quality...")
    
    # main.pyのprocess_session関数から品質向上処理をインポート
    # ここでは簡略化のため、regenerate_mesh.pyの関数を使用
    from regenerate_mesh import improve_mesh_quality
    
    mesh = improve_mesh_quality(mesh, CONFIG, job_id)
    
    print("")
    print("Step 5: Saving results...")
    
    # 点群を保存
    pcd_path = result_dir / "point_cloud.ply"
    o3d.io.write_point_cloud(str(pcd_path), pcd, write_ascii=False)
    print(f"✓ Saved point cloud: {pcd_path}")
    
    # メッシュを保存（簡略化設定を適用）
    output_config = CONFIG.get('output', {})
    mesh_output_config = output_config.get('mesh', {})
    simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)
    max_triangles = mesh_output_config.get('max_triangles_for_viewer', 500000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    # 簡略化する前に元のメッシュを保存
    if simplify_for_viewer and original_triangles > max_triangles:
        original_mesh_path = result_dir / "mesh_original.ply"
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
            
            mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
            if len(mesh_simplified.triangles) > 0:
                mesh_simplified.remove_duplicated_triangles()
                mesh_simplified.remove_duplicated_vertices()
                mesh_simplified.remove_non_manifold_edges()
                mesh_simplified.compute_vertex_normals()
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified mesh: {len(mesh_simplified.triangles)} triangles")
        except Exception as e:
            print(f"⚠ Simplification failed: {e}, using original mesh")
    
    # メッシュを保存（ASCII形式）
    mesh_path = result_dir / "mesh.ply"
    o3d.io.write_triangle_mesh(
        str(mesh_path),
        mesh_to_save,
        write_ascii=True,
        compressed=False
    )
    print(f"✓ Saved mesh: {mesh_path}")
    print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
    print("")
    
    print("✅ Job reprocessed successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reprocess_job.py <job_id>")
        print("Example: python reprocess_job.py 2151df2e")
        sys.exit(1)
    
    job_id = sys.argv[1]
    success = reprocess_job(job_id)
    sys.exit(0 if success else 1)

既存のジョブデータを再処理するスクリプト（MiDaS深度推定を使用）
セッションデータからRGB-D統合をやり直し、更新された設定でメッシュを生成
"""

import sys
import yaml
import open3d as o3d
from pathlib import Path
from typing import Dict, Any

# main.pyと同じ処理パイプラインを使用
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser

# GPU対応版を優先的に使用
try:
    from pipeline.rgbd_integration_gpu import RGBDIntegrationGPU as RGBDIntegration
    from pipeline.mesh_generation_gpu import create_mesh_from_rgbd_volume_gpu as create_mesh_from_rgbd_volume
    GPU_AVAILABLE = True
    print("✓ Using GPU-accelerated pipeline")
except ImportError:
    from pipeline.rgbd_integration import RGBDIntegration
    from pipeline.mesh_generation import create_mesh_from_rgbd_volume
    GPU_AVAILABLE = False
    print("⚠ GPU pipeline not available, using CPU pipeline")

# main.pyと同じ処理ロジックを使用
from main import (
    load_config, CONFIG,
    PROCESSING_CONFIG, GPU_CONFIG, DEPTH_ESTIMATION_CONFIG,
    RESULTS_DIR
)

def reprocess_job(job_id: str):
    """既存のジョブを再処理"""
    session_dir = Path(f"/opt/arcore-open3d-gpu/data/sessions/{job_id}")
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        return False
    
    result_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Reprocessing job: {job_id}")
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
    
    print(f"Frames: {len(parser.frames)}, Has depth: {parser.has_depth_data()}")
    print("")
    
    # RGB-D統合（MiDaS深度推定を強制使用）
    print("Step 2: RGB-D integration with MiDaS depth estimation...")
    
    if GPU_AVAILABLE:
        integration = RGBDIntegration(PROCESSING_CONFIG, GPU_CONFIG)
    else:
        integration = RGBDIntegration(PROCESSING_CONFIG)
    
    # 深度推定を強制使用
    force_depth_estimation = DEPTH_ESTIMATION_CONFIG.get('force_use', True)
    
    def progress_cb(p, m):
        print(f"  Progress: {p}% - {m}")
    
    if not integration.process_session(parser, progress_cb, force_depth_estimation=force_depth_estimation):
        print("Error: RGB-D integration failed")
        return False
    
    print("")
    print("Step 3: Extracting point cloud and mesh...")
    
    # 点群とメッシュを抽出
    if GPU_AVAILABLE:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG, GPU_CONFIG)
    else:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG)
    
    if pcd is None or len(pcd.points) == 0:
        print("Error: Failed to extract point cloud")
        return False
    
    if mesh is None or len(mesh.triangles) == 0:
        print("Error: Failed to extract mesh")
        return False
    
    print(f"Extracted point cloud: {len(pcd.points)} points")
    print(f"Extracted mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    print("")
    
    # main.pyと同じ品質向上処理を適用
    print("Step 4: Improving mesh quality...")
    
    # main.pyのprocess_session関数から品質向上処理をインポート
    # ここでは簡略化のため、regenerate_mesh.pyの関数を使用
    from regenerate_mesh import improve_mesh_quality
    
    mesh = improve_mesh_quality(mesh, CONFIG, job_id)
    
    print("")
    print("Step 5: Saving results...")
    
    # 点群を保存
    pcd_path = result_dir / "point_cloud.ply"
    o3d.io.write_point_cloud(str(pcd_path), pcd, write_ascii=False)
    print(f"✓ Saved point cloud: {pcd_path}")
    
    # メッシュを保存（簡略化設定を適用）
    output_config = CONFIG.get('output', {})
    mesh_output_config = output_config.get('mesh', {})
    simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)
    max_triangles = mesh_output_config.get('max_triangles_for_viewer', 500000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    # 簡略化する前に元のメッシュを保存
    if simplify_for_viewer and original_triangles > max_triangles:
        original_mesh_path = result_dir / "mesh_original.ply"
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
            
            mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
            if len(mesh_simplified.triangles) > 0:
                mesh_simplified.remove_duplicated_triangles()
                mesh_simplified.remove_duplicated_vertices()
                mesh_simplified.remove_non_manifold_edges()
                mesh_simplified.compute_vertex_normals()
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified mesh: {len(mesh_simplified.triangles)} triangles")
        except Exception as e:
            print(f"⚠ Simplification failed: {e}, using original mesh")
    
    # メッシュを保存（ASCII形式）
    mesh_path = result_dir / "mesh.ply"
    o3d.io.write_triangle_mesh(
        str(mesh_path),
        mesh_to_save,
        write_ascii=True,
        compressed=False
    )
    print(f"✓ Saved mesh: {mesh_path}")
    print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
    print("")
    
    print("✅ Job reprocessed successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reprocess_job.py <job_id>")
        print("Example: python reprocess_job.py 2151df2e")
        sys.exit(1)
    
    job_id = sys.argv[1]
    success = reprocess_job(job_id)
    sys.exit(0 if success else 1)

既存のジョブデータを再処理するスクリプト（MiDaS深度推定を使用）
セッションデータからRGB-D統合をやり直し、更新された設定でメッシュを生成
"""

import sys
import yaml
import open3d as o3d
from pathlib import Path
from typing import Dict, Any

# main.pyと同じ処理パイプラインを使用
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser

# GPU対応版を優先的に使用
try:
    from pipeline.rgbd_integration_gpu import RGBDIntegrationGPU as RGBDIntegration
    from pipeline.mesh_generation_gpu import create_mesh_from_rgbd_volume_gpu as create_mesh_from_rgbd_volume
    GPU_AVAILABLE = True
    print("✓ Using GPU-accelerated pipeline")
except ImportError:
    from pipeline.rgbd_integration import RGBDIntegration
    from pipeline.mesh_generation import create_mesh_from_rgbd_volume
    GPU_AVAILABLE = False
    print("⚠ GPU pipeline not available, using CPU pipeline")

# main.pyと同じ処理ロジックを使用
from main import (
    load_config, CONFIG,
    PROCESSING_CONFIG, GPU_CONFIG, DEPTH_ESTIMATION_CONFIG,
    RESULTS_DIR
)

def reprocess_job(job_id: str):
    """既存のジョブを再処理"""
    session_dir = Path(f"/opt/arcore-open3d-gpu/data/sessions/{job_id}")
    result_dir = RESULTS_DIR / job_id
    
    if not session_dir.exists():
        print(f"Error: Session directory not found: {session_dir}")
        return False
    
    result_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Reprocessing job: {job_id}")
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
    
    print(f"Frames: {len(parser.frames)}, Has depth: {parser.has_depth_data()}")
    print("")
    
    # RGB-D統合（MiDaS深度推定を強制使用）
    print("Step 2: RGB-D integration with MiDaS depth estimation...")
    
    if GPU_AVAILABLE:
        integration = RGBDIntegration(PROCESSING_CONFIG, GPU_CONFIG)
    else:
        integration = RGBDIntegration(PROCESSING_CONFIG)
    
    # 深度推定を強制使用
    force_depth_estimation = DEPTH_ESTIMATION_CONFIG.get('force_use', True)
    
    def progress_cb(p, m):
        print(f"  Progress: {p}% - {m}")
    
    if not integration.process_session(parser, progress_cb, force_depth_estimation=force_depth_estimation):
        print("Error: RGB-D integration failed")
        return False
    
    print("")
    print("Step 3: Extracting point cloud and mesh...")
    
    # 点群とメッシュを抽出
    if GPU_AVAILABLE:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG, GPU_CONFIG)
    else:
        pcd, mesh = create_mesh_from_rgbd_volume(integration.volume, CONFIG)
    
    if pcd is None or len(pcd.points) == 0:
        print("Error: Failed to extract point cloud")
        return False
    
    if mesh is None or len(mesh.triangles) == 0:
        print("Error: Failed to extract mesh")
        return False
    
    print(f"Extracted point cloud: {len(pcd.points)} points")
    print(f"Extracted mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    print("")
    
    # main.pyと同じ品質向上処理を適用
    print("Step 4: Improving mesh quality...")
    
    # main.pyのprocess_session関数から品質向上処理をインポート
    # ここでは簡略化のため、regenerate_mesh.pyの関数を使用
    from regenerate_mesh import improve_mesh_quality
    
    mesh = improve_mesh_quality(mesh, CONFIG, job_id)
    
    print("")
    print("Step 5: Saving results...")
    
    # 点群を保存
    pcd_path = result_dir / "point_cloud.ply"
    o3d.io.write_point_cloud(str(pcd_path), pcd, write_ascii=False)
    print(f"✓ Saved point cloud: {pcd_path}")
    
    # メッシュを保存（簡略化設定を適用）
    output_config = CONFIG.get('output', {})
    mesh_output_config = output_config.get('mesh', {})
    simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)
    max_triangles = mesh_output_config.get('max_triangles_for_viewer', 500000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    # 簡略化する前に元のメッシュを保存
    if simplify_for_viewer and original_triangles > max_triangles:
        original_mesh_path = result_dir / "mesh_original.ply"
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
            
            mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
            if len(mesh_simplified.triangles) > 0:
                mesh_simplified.remove_duplicated_triangles()
                mesh_simplified.remove_duplicated_vertices()
                mesh_simplified.remove_non_manifold_edges()
                mesh_simplified.compute_vertex_normals()
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified mesh: {len(mesh_simplified.triangles)} triangles")
        except Exception as e:
            print(f"⚠ Simplification failed: {e}, using original mesh")
    
    # メッシュを保存（ASCII形式）
    mesh_path = result_dir / "mesh.ply"
    o3d.io.write_triangle_mesh(
        str(mesh_path),
        mesh_to_save,
        write_ascii=True,
        compressed=False
    )
    print(f"✓ Saved mesh: {mesh_path}")
    print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
    print("")
    
    print("✅ Job reprocessed successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reprocess_job.py <job_id>")
        print("Example: python reprocess_job.py 2151df2e")
        sys.exit(1)
    
    job_id = sys.argv[1]
    success = reprocess_job(job_id)
    sys.exit(0 if success else 1)
