#!/usr/bin/env python3
"""
既存データのメッシュを再生成するスクリプト
点群からメッシュを再生成し、yaml設定に基づいて品質向上処理を適用します
"""

import sys
import yaml
import numpy as np
import open3d as o3d
from pathlib import Path
from typing import Dict, Any

# 設定読み込み
CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {}

def improve_mesh_quality(mesh: o3d.geometry.TriangleMesh, config: Dict[str, Any], job_id: str = "") -> o3d.geometry.TriangleMesh:
    """メッシュの品質向上処理（main.pyと同じ処理）"""
    # 1. メッシュのクリーンアップ
    print(f"{'[' + job_id + '] ' if job_id else ''}Cleaning up mesh...")
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    
    # 2. メッシュの平滑化（yaml設定を適用）
    mesh_config = config.get('mesh', {})
    smoothing_config = mesh_config.get('smoothing', {})
    if smoothing_config.get('enable', True):
        iterations = smoothing_config.get('iterations', 5)
        lambda_filter = smoothing_config.get('lambda_filter', 0.5)
        method = smoothing_config.get('method', 'laplacian')
        
        print(f"{'[' + job_id + '] ' if job_id else ''}Smoothing mesh ({method}, {iterations} iterations, lambda={lambda_filter})...")
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
                    mu=-0.53  # Taubinパラメータ
                )
            else:
                print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Unknown smoothing method: {method}, using laplacian")
                mesh = mesh.filter_smooth_laplacian(
                    number_of_iterations=iterations,
                    lambda_filter=lambda_filter
                )
            mesh.compute_vertex_normals()
            print(f"{'[' + job_id + '] ' if job_id else ''}✓ Mesh smoothed")
        except Exception as e:
            print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Smoothing error: {e}")
    
    return mesh

def regenerate_mesh_from_pointcloud(job_id: str, config: Dict[str, Any] = None):
    """点群からメッシュを再生成"""
    if config is None:
        config = load_config()
    
    results_dir = Path("/opt/arcore-open3d-gpu/data/results")
    pcd_path = results_dir / job_id / "point_cloud.ply"
    mesh_path = results_dir / job_id / "mesh.ply"
    
    if not pcd_path.exists():
        print(f"Error: Point cloud file not found: {pcd_path}")
        return False
    
    print(f"Reading point cloud from: {pcd_path}")
    pcd = o3d.io.read_point_cloud(str(pcd_path))
    
    if len(pcd.points) == 0:
        print("Error: Point cloud is empty!")
        return False
    
    print(f"Point cloud: {len(pcd.points)} points")
    
    # メッシュ生成
    from pipeline.mesh_generation_gpu import MeshGeneratorGPU
    
    mesh_config = config.get('mesh', {})
    gpu_config = config.get('gpu', {})
    
    print(f"Generating mesh from point cloud...")
    mesh_gen = MeshGeneratorGPU(mesh_config, gpu_config)
    mesh = mesh_gen.generate(pcd)
    
    if mesh is None or len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
        print("Error: Mesh generation failed!")
        return False
    
    print(f"Generated mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    
    # メッシュに色を追加
    if not mesh.has_vertex_colors():
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
    
    # 品質向上処理（yaml設定を適用）
    mesh = improve_mesh_quality(mesh, config, job_id)
    
    # 簡略化（必要に応じて）
    output_config = config.get('output', {})
    max_triangles = output_config.get('mesh', {}).get('max_triangles_for_viewer', 1000000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    if original_triangles > max_triangles:
        print(f"Simplifying mesh to {max_triangles} triangles...")
        try:
            mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
            if len(mesh_simplified.triangles) > 0:
                mesh_simplified.remove_duplicated_triangles()
                mesh_simplified.remove_duplicated_vertices()
                mesh_simplified.remove_non_manifold_edges()
                mesh_simplified.compute_vertex_normals()
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified: {len(mesh_simplified.triangles)} triangles ({original_triangles} -> {len(mesh_simplified.triangles)})")
            else:
                print("⚠ Simplification failed, using original mesh")
        except Exception as e:
            print(f"⚠ Simplification error: {e}, using original mesh")
    
    # ASCII形式で保存
    print(f"Saving mesh to: {mesh_path}")
    try:
        o3d.io.write_triangle_mesh(
            str(mesh_path),
            mesh_to_save,
            write_ascii=True,
            compressed=False
        )
        print(f"✓ Mesh saved successfully")
        print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
        return True
    except Exception as e:
        print(f"Error saving mesh: {e}")
        import traceback
        traceback.print_exc()
        return False

def regenerate_mesh_from_existing(job_id: str, config: Dict[str, Any] = None):
    """既存のメッシュを読み込んで品質向上処理を適用"""
    if config is None:
        config = load_config()
    
    results_dir = Path("/opt/arcore-open3d-gpu/data/results")
    mesh_path = results_dir / job_id / "mesh.ply"
    
    if not mesh_path.exists():
        print(f"Error: Mesh file not found: {mesh_path}")
        return False
    
    print(f"Reading mesh from: {mesh_path}")
    mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    
    if len(mesh.vertices) == 0 or len(mesh.triangles) == 0:
        print("Error: Mesh is empty!")
        return False
    
    print(f"Original mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
    
    # 品質向上処理（yaml設定を適用）
    mesh = improve_mesh_quality(mesh, config, job_id)
    
    # 簡略化（必要に応じて）
    output_config = config.get('output', {})
    max_triangles = output_config.get('mesh', {}).get('max_triangles_for_viewer', 1000000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    if original_triangles > max_triangles:
        print(f"Simplifying mesh to {max_triangles} triangles...")
        try:
            mesh_simplified = mesh.simplify_quadric_decimation(max_triangles)
            if len(mesh_simplified.triangles) > 0:
                mesh_simplified.remove_duplicated_triangles()
                mesh_simplified.remove_duplicated_vertices()
                mesh_simplified.remove_non_manifold_edges()
                mesh_simplified.compute_vertex_normals()
                mesh_to_save = mesh_simplified
                print(f"✓ Simplified: {len(mesh_simplified.triangles)} triangles ({original_triangles} -> {len(mesh_simplified.triangles)})")
            else:
                print("⚠ Simplification failed, using original mesh")
        except Exception as e:
            print(f"⚠ Simplification error: {e}, using original mesh")
    
    # ASCII形式で保存
    print(f"Saving mesh to: {mesh_path}")
    try:
        o3d.io.write_triangle_mesh(
            str(mesh_path),
            mesh_to_save,
            write_ascii=True,
            compressed=False
        )
        print(f"✓ Mesh saved successfully")
        print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
        return True
    except Exception as e:
        print(f"Error saving mesh: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python regenerate_mesh.py <job_id> [mode]")
        print("  mode: 'pointcloud' (from point cloud) or 'existing' (from existing mesh)")
        print("Example: python regenerate_mesh.py 1611626e pointcloud")
        print("Example: python regenerate_mesh.py 1611626e existing")
        sys.exit(1)
    
    job_id = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "existing"
    
    config = load_config()
    
    if mode == "pointcloud":
        success = regenerate_mesh_from_pointcloud(job_id, config)
    else:
        success = regenerate_mesh_from_existing(job_id, config)
    
    sys.exit(0 if success else 1)

