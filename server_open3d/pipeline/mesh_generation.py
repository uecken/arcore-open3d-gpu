"""
Mesh Generation Pipeline
Open3D Surface Reconstruction
"""

import numpy as np
from typing import Optional, Dict, Any, Tuple
import open3d as o3d


class MeshGenerator:
    """
    点群からメッシュを生成
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 設定辞書
        """
        self.config = config or {}
        mesh_config = self.config.get('mesh', {})
        
        self.method = mesh_config.get('method', 'poisson')
        self.poisson_config = mesh_config.get('poisson', {})
        self.ball_pivoting_config = mesh_config.get('ball_pivoting', {})
        self.alpha_config = mesh_config.get('alpha_shape', {})
    
    def generate(self, 
                 pcd: o3d.geometry.PointCloud,
                 method: str = None) -> Optional[o3d.geometry.TriangleMesh]:
        """
        点群からメッシュを生成
        
        Args:
            pcd: 入力点群
            method: 生成手法 ('poisson', 'ball_pivoting', 'alpha_shape')
            
        Returns:
            生成されたメッシュ
        """
        method = method or self.method
        
        if len(pcd.points) < 10:
            print("Not enough points for mesh generation")
            return None
        
        # 法線がなければ計算
        if not pcd.has_normals():
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
            )
            pcd.orient_normals_consistent_tangent_plane(30)
        
        if method == 'poisson':
            return self._poisson_reconstruction(pcd)
        elif method == 'ball_pivoting':
            return self._ball_pivoting(pcd)
        elif method == 'alpha_shape':
            return self._alpha_shape(pcd)
        else:
            print(f"Unknown method: {method}")
            return None
    
    def _poisson_reconstruction(self, 
                                 pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        """
        Poisson Surface Reconstruction
        
        高品質で穴の少ないメッシュを生成
        """
        depth = self.poisson_config.get('depth', 9)
        width = self.poisson_config.get('width', 0)
        scale = self.poisson_config.get('scale', 1.1)
        linear_fit = self.poisson_config.get('linear_fit', False)
        
        print(f"Poisson reconstruction (depth={depth})...")
        
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd,
            depth=depth,
            width=width,
            scale=scale,
            linear_fit=linear_fit
        )
        
        # 密度でフィルタリング（低密度の三角形を除去）
        densities = np.asarray(densities)
        percentile = self.poisson_config.get('density_threshold_percentile', 10)
        density_threshold = np.quantile(densities, percentile / 100.0)
        vertices_to_remove = densities < density_threshold
        mesh.remove_vertices_by_mask(vertices_to_remove)
        
        mesh.compute_vertex_normals()
        
        # メッシュ平滑化
        mesh_config = self.config.get('mesh', {})
        smoothing_config = mesh_config.get('smoothing', {})
        
        if smoothing_config.get('enable', False):
            method = smoothing_config.get('method', 'laplacian')
            iterations = smoothing_config.get('iterations', 5)
            lambda_filter = smoothing_config.get('lambda_filter', 0.5)
            
            if method == 'laplacian':
                mesh = mesh.filter_smooth_laplacian(
                    number_of_iterations=iterations,
                    lambda_filter=lambda_filter
                )
            elif method == 'taubin':
                mu = -0.53  # Taubin filterの推奨値
                mesh = mesh.filter_smooth_taubin(
                    number_of_iterations=iterations,
                    lambda_filter=lambda_filter,
                    mu=mu
                )
            
            mesh.compute_vertex_normals()
        
        # メッシュ最適化
        optimization_config = mesh_config.get('optimization', {})
        if optimization_config.get('enable', True):
            mesh = self.clean_mesh(mesh)
            
            if optimization_config.get('orient_normals', True):
                mesh.compute_vertex_normals()
        
        return mesh
    
    def _ball_pivoting(self, 
                       pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        """
        Ball Pivoting Algorithm
        
        高速だが穴ができやすい
        """
        radii = self.ball_pivoting_config.get('radii', [0.005, 0.01, 0.02, 0.04])
        radii = o3d.utility.DoubleVector(radii)
        
        print(f"Ball pivoting (radii={list(radii)})...")
        
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, radii
        )
        
        mesh.compute_vertex_normals()
        
        return mesh
    
    def _alpha_shape(self, 
                     pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        """
        Alpha Shape
        
        点群の境界を囲むメッシュ
        """
        alpha = self.alpha_config.get('alpha', 0.03)
        
        print(f"Alpha shape (alpha={alpha})...")
        
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(
            pcd, alpha
        )
        
        mesh.compute_vertex_normals()
        
        return mesh
    
    @staticmethod
    def simplify_mesh(mesh: o3d.geometry.TriangleMesh, 
                      target_triangles: int = 100000) -> o3d.geometry.TriangleMesh:
        """
        メッシュを簡略化
        
        Args:
            mesh: 入力メッシュ
            target_triangles: 目標三角形数
            
        Returns:
            簡略化されたメッシュ
        """
        current_triangles = len(mesh.triangles)
        
        if current_triangles <= target_triangles:
            return mesh
        
        print(f"Simplifying mesh: {current_triangles} -> {target_triangles} triangles")
        
        mesh = mesh.simplify_quadric_decimation(target_triangles)
        mesh.compute_vertex_normals()
        
        return mesh
    
    @staticmethod
    def clean_mesh(mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
        """
        メッシュをクリーンアップ
        
        - 重複頂点を除去
        - 孤立頂点を除去
        - 非多様体エッジを除去
        """
        mesh.remove_duplicated_vertices()
        mesh.remove_duplicated_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.remove_degenerate_triangles()
        mesh.compute_vertex_normals()
        
        return mesh
    
    @staticmethod
    def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> Dict[str, Any]:
        """
        メッシュ情報を取得
        """
        return {
            "vertices": len(mesh.vertices),
            "triangles": len(mesh.triangles),
            "has_normals": mesh.has_vertex_normals(),
            "has_colors": mesh.has_vertex_colors(),
            "is_watertight": mesh.is_watertight(),
            "surface_area": mesh.get_surface_area(),
            "volume": mesh.get_volume() if mesh.is_watertight() else None
        }


def create_mesh_from_rgbd_volume(volume: o3d.pipelines.integration.ScalableTSDFVolume,
                                  config: Dict[str, Any] = None) -> Tuple[o3d.geometry.PointCloud, 
                                                                          o3d.geometry.TriangleMesh]:
    """
    TSDF Volumeから点群とメッシュを抽出
    
    Args:
        volume: TSDF Volume
        config: 設定辞書
        
    Returns:
        (点群, メッシュ)
    """
    # メッシュ抽出
    mesh = volume.extract_triangle_mesh()
    mesh.compute_vertex_normals()
    
    # 点群抽出
    pcd = volume.extract_point_cloud()
    
    # メッシュクリーンアップ
    mesh = MeshGenerator.clean_mesh(mesh)
    
    # 簡略化（オプション）
    output_config = config.get('output', {}) if config else {}
    if output_config.get('simplify', False):
        target = output_config.get('target_triangles', 100000)
        mesh = MeshGenerator.simplify_mesh(mesh, target)
    
    return pcd, mesh

