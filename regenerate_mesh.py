#!/usr/bin/env python3
"""
既存データのメッシュを再生成するスクリプト（GPU対応版）
点群からメッシュを再生成し、yaml設定に基づいて品質向上処理を適用します
GPU対応版のMeshGeneratorを使用して高速処理を実現します
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

def check_gpu_availability(gpu_config: Dict[str, Any]) -> bool:
    """GPUが利用可能か確認"""
    if not gpu_config.get('enabled', True):
        return False
    
    try:
        import torch
        if torch.cuda.is_available() and gpu_config.get('use_cuda', True):
            device_id = gpu_config.get('device_id', 0)
            gpu_name = torch.cuda.get_device_name(device_id)
            print(f"✓ GPU available: {gpu_name} (Device {device_id})")
            return True
        else:
            print("⚠ GPU not available (CUDA not available)")
            return False
    except ImportError:
        print("⚠ GPU not available (PyTorch not installed)")
        return False
    except Exception as e:
        print(f"⚠ GPU check error: {e}")
        return False

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
                    print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Large mesh ({triangle_count} triangles), skipping subdivision to prevent memory issues")
                    subdiv_iterations = 0
                
                if subdiv_iterations > 0:
                    print(f"{'[' + job_id + '] ' if job_id else ''}Checking mesh manifoldness before subdivision...")
                    try:
                        # メッシュの多様体性を確認
                        is_edge_manifold = mesh.is_edge_manifold(allow_boundary_edges=True)
                        is_vertex_manifold = mesh.is_vertex_manifold()
                        
                        if not is_edge_manifold or not is_vertex_manifold:
                            print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Mesh is not manifold (edge_manifold: {is_edge_manifold}, vertex_manifold: {is_vertex_manifold})")
                            print(f"{'[' + job_id + '] ' if job_id else ''}   Attempting to fix non-manifold mesh...")
                            
                            # 非多様体エッジを削除
                            mesh.remove_non_manifold_edges()
                            # non-manifold verticesの削除（Open3Dには直接的なメソッドがないため、
                            # remove_non_manifold_edges()とremove_unreferenced_vertices()で対応）
                            mesh.remove_duplicated_triangles()
                            mesh.remove_duplicated_vertices()
                            mesh.remove_unreferenced_vertices()
                            
                            # 再度確認
                            is_edge_manifold = mesh.is_edge_manifold(allow_boundary_edges=True)
                            is_vertex_manifold = mesh.is_vertex_manifold()
                            
                            if not is_edge_manifold or not is_vertex_manifold:
                                print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Mesh is still not manifold, skipping subdivision to prevent errors")
                                subdiv_iterations = 0
                            else:
                                print(f"{'[' + job_id + '] ' if job_id else ''}✓ Mesh is now manifold, proceeding with subdivision")
                        
                        if subdiv_iterations > 0:
                            # 反復回数を制限（メモリ保護）
                            max_iterations = subdivision_config.get('max_iterations', 1)
                            subdiv_iterations = min(subdiv_iterations, max_iterations)
                            
                            print(f"{'[' + job_id + '] ' if job_id else ''}Subdividing mesh ({subdiv_method}, {subdiv_iterations} iterations)...")
                            
                            if subdiv_method == 'loop':
                                mesh = mesh.subdivide_loop(number_of_iterations=subdiv_iterations)
                            elif subdiv_method == 'midpoint':
                                mesh = mesh.subdivide_midpoint(number_of_iterations=subdiv_iterations)
                            else:
                                print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Unknown subdivision method: {subdiv_method}, using loop")
                                mesh = mesh.subdivide_loop(number_of_iterations=subdiv_iterations)
                            
                            # 細分化後のクリーンアップ
                            mesh.remove_duplicated_triangles()
                            mesh.remove_duplicated_vertices()
                            mesh.remove_non_manifold_edges()
                            mesh.compute_vertex_normals()
                            
                            print(f"{'[' + job_id + '] ' if job_id else ''}✓ Mesh subdivided: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
                    except Exception as e:
                        print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Subdivision error: {e}")
                        import traceback
                        traceback.print_exc()
                        # エラーが発生した場合は細分化をスキップして続行
        
        # 3-2. 法線の改善
        normal_config = quality_config.get('normal_improvement', {})
        if normal_config.get('enable', True):
            print(f"{'[' + job_id + '] ' if job_id else ''}Improving normals...")
            try:
                mesh.compute_vertex_normals(normalized=True)
                if normal_config.get('smooth_normals', True):
                    mesh.normalize_normals()
                print(f"{'[' + job_id + '] ' if job_id else ''}✓ Normals improved")
            except Exception as e:
                print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Normal improvement error: {e}")
        
        # 3-3. 色の補正と強化
        color_config = quality_config.get('color_enhancement', {})
        if color_config.get('enable', True) and mesh.has_vertex_colors():
            print(f"{'[' + job_id + '] ' if job_id else ''}Enhancing colors...")
            try:
                colors = np.asarray(mesh.vertex_colors)
                contrast = color_config.get('contrast', 1.0)
                saturation = color_config.get('saturation', 1.0)
                brightness = color_config.get('brightness', 1.0)
                
                # コントラスト調整
                if contrast != 1.0:
                    colors = (colors - 0.5) * contrast + 0.5
                
                # 彩度調整
                if saturation != 1.0:
                    gray = np.mean(colors, axis=1, keepdims=True)
                    colors = gray + (colors - gray) * saturation
                
                # 明度調整
                if brightness != 1.0:
                    colors = colors * brightness
                
                colors = np.clip(colors, 0, 1)
                mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                print(f"{'[' + job_id + '] ' if job_id else ''}✓ Colors enhanced (contrast={contrast}, saturation={saturation}, brightness={brightness})")
            except Exception as e:
                print(f"{'[' + job_id + '] ' if job_id else ''}⚠ Color enhancement error: {e}")
    
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
    
    # GPU設定の確認
    gpu_config = config.get('gpu', {})
    gpu_available = check_gpu_availability(gpu_config)
    
    # メッシュ生成（GPU対応版を優先的に使用）
    mesh_config = config.get('mesh', {})
    
    if gpu_available:
        try:
            from pipeline.mesh_generation_gpu import MeshGeneratorGPU
            print(f"Generating mesh from point cloud (GPU accelerated)...")
            mesh_gen = MeshGeneratorGPU(mesh_config, gpu_config)
            if mesh_gen.use_gpu:
                print(f"  Using GPU device: {mesh_gen.o3d_device}")
            else:
                print(f"  GPU initialization failed, using CPU")
            mesh = mesh_gen.generate(pcd)
        except ImportError:
            print("⚠ GPU pipeline not available, falling back to CPU")
            from pipeline.mesh_generation import MeshGenerator
            mesh_gen = MeshGenerator(mesh_config)
            mesh = mesh_gen.generate(pcd)
        except Exception as e:
            print(f"⚠ GPU mesh generation error: {e}, falling back to CPU")
            from pipeline.mesh_generation import MeshGenerator
            mesh_gen = MeshGenerator(mesh_config)
            mesh = mesh_gen.generate(pcd)
    else:
        # CPU版を使用
        from pipeline.mesh_generation import MeshGenerator
        print(f"Generating mesh from point cloud (CPU)...")
        mesh_gen = MeshGenerator(mesh_config)
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
    
    # 簡略化（必要に応じて、設定でON/OFF可能）
    output_config = config.get('output', {})
    mesh_output_config = output_config.get('mesh', {})
    simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)  # デフォルト: true
    max_triangles = mesh_output_config.get('max_triangles_for_viewer', 1000000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    # 簡略化する前に元のメッシュを保存
    original_mesh_path = results_dir / job_id / "mesh_original.ply"
    save_original = False
    
    if simplify_for_viewer and original_triangles > max_triangles:
        print(f"Simplifying mesh to {max_triangles} triangles...")
        # 簡略化前に元のメッシュを保存
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            save_original = True
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
        except Exception as e:
            print(f"⚠ Failed to save original mesh: {e}")
        
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
    elif not simplify_for_viewer:
        print(f"⚠ Viewer simplification is disabled (simplify_for_viewer=false), using original mesh ({original_triangles} triangles)")
    
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
    
    # 簡略化（必要に応じて、設定でON/OFF可能）
    output_config = config.get('output', {})
    mesh_output_config = output_config.get('mesh', {})
    simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)  # デフォルト: true
    max_triangles = mesh_output_config.get('max_triangles_for_viewer', 1000000)
    
    original_triangles = len(mesh.triangles)
    mesh_to_save = mesh
    
    # 簡略化する前に元のメッシュを保存
    original_mesh_path = results_dir / job_id / "mesh_original.ply"
    save_original = False
    
    if simplify_for_viewer and original_triangles > max_triangles:
        print(f"Simplifying mesh to {max_triangles} triangles...")
        # 簡略化前に元のメッシュを保存
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            save_original = True
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
        except Exception as e:
            print(f"⚠ Failed to save original mesh: {e}")
        
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
    elif not simplify_for_viewer:
        print(f"⚠ Viewer simplification is disabled (simplify_for_viewer=false), using original mesh ({original_triangles} triangles)")
    
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
        print("")
        print("GPU対応版: yaml設定のgpu.enabled=trueでGPU加速が有効になります")
        sys.exit(1)
    
    job_id = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "existing"
    
    config = load_config()
    
    # GPU設定の確認と表示
    gpu_config = config.get('gpu', {})
    if gpu_config.get('enabled', True):
        print("=" * 60)
        print("GPU対応版 メッシュ再生成スクリプト")
        print("=" * 60)
        check_gpu_availability(gpu_config)
        print("")
    else:
        print("GPU is disabled in config.yaml, using CPU")
        print("")
    
    if mode == "pointcloud":
        success = regenerate_mesh_from_pointcloud(job_id, config)
    else:
        success = regenerate_mesh_from_existing(job_id, config)
    
    sys.exit(0 if success else 1)

    job_id = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "existing"
    
    config = load_config()
    
    # GPU設定の確認と表示
    gpu_config = config.get('gpu', {})
    if gpu_config.get('enabled', True):
        print("=" * 60)
        print("GPU対応版 メッシュ再生成スクリプト")
        print("=" * 60)
        check_gpu_availability(gpu_config)
        print("")
    else:
        print("GPU is disabled in config.yaml, using CPU")
        print("")
    
    if mode == "pointcloud":
        success = regenerate_mesh_from_pointcloud(job_id, config)
    else:
        success = regenerate_mesh_from_existing(job_id, config)
    
    sys.exit(0 if success else 1)
