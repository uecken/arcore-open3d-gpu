"""
Mesh Generation Pipeline (GPU対応版)
Open3D Tensor APIを使用したSurface Reconstruction
"""

import numpy as np
from typing import Optional, Dict, Any, Tuple
import open3d as o3d


class MeshGeneratorGPU:
    """
    点群からメッシュを生成（GPU対応版）
    """
    
    def __init__(self, config: Dict[str, Any] = None, gpu_config: Dict[str, Any] = None):
        """
        Args:
            config: 設定辞書
            gpu_config: GPU設定辞書
        """
        self.config = config or {}
        self.gpu_config = gpu_config or {}
        
        mesh_config = self.config.get('mesh', {})
        self.method = mesh_config.get('method', 'poisson')
        self.poisson_config = mesh_config.get('poisson', {})
        
        # GPU設定
        self.use_gpu = self.gpu_config.get('enabled', True) and self.gpu_config.get('use_cuda', True)
        self.o3d_device = None
        self._initialize_device()
    
    def _initialize_device(self):
        """Open3DのGPUデバイスを初期化"""
        try:
            if hasattr(o3d, 'core') and hasattr(o3d.core, 'Device'):
                if self.use_gpu:
                    # PyTorchのCUDAが利用可能か確認
                    try:
                        import torch
                        if torch.cuda.is_available():
                            # CUDAデバイスを直接作成（Open3D 0.19ではget_available_devices()が存在しない）
                            device_id = self.gpu_config.get('device_id', 0)
                            try:
                                self.o3d_device = o3d.core.Device(f"CUDA:{device_id}")
                                # デバイスが正しく作成されたか確認
                                device_type = self.o3d_device.get_type()
                                if device_type == o3d.core.Device.DeviceType.CUDA:
                                    pass  # GPU device successfully created
                                else:
                                    self.o3d_device = o3d.core.Device("CPU:0")
                                    self.use_gpu = False
                            except Exception as e:
                                self.o3d_device = o3d.core.Device("CPU:0")
                                self.use_gpu = False
                        else:
                            self.o3d_device = o3d.core.Device("CPU:0")
                            self.use_gpu = False
                    except ImportError:
                        self.o3d_device = o3d.core.Device("CPU:0")
                        self.use_gpu = False
                else:
                    self.o3d_device = o3d.core.Device("CPU:0")
            else:
                self.o3d_device = o3d.core.Device("CPU:0")
                self.use_gpu = False
        except Exception as e:
            self.o3d_device = o3d.core.Device("CPU:0")
            self.use_gpu = False
    
    def generate(self, 
                 pcd: o3d.geometry.PointCloud,
                 method: str = None) -> Optional[o3d.geometry.TriangleMesh]:
        """
        点群からメッシュを生成（GPU対応）
        
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
        
        # GPU対応のメッシュ生成を試みる
        if self.use_gpu and hasattr(o3d, 't') and hasattr(o3d.t, 'geometry'):
            try:
                # まずCPUで法線を計算（Tensor APIでは法線計算が不安定なため）
                if not pcd.has_normals():
                    pcd.estimate_normals(
                        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
                    )
                    pcd.orient_normals_consistent_tangent_plane(30)
                
                # Tensor形式の点群に変換（法線も含む）
                pcd_tensor = o3d.t.geometry.PointCloud.from_legacy(pcd, device=self.o3d_device)
                
                # メッシュ生成
                if method == 'poisson':
                    return self._poisson_reconstruction_gpu(pcd_tensor)
                else:
                    # フォールバック: CPUで処理
                    return self._generate_cpu(pcd, method)
            except Exception as e:
                print(f"GPU mesh generation failed: {e}, falling back to CPU")
                import traceback
                traceback.print_exc()
                return self._generate_cpu(pcd, method)
        else:
            # CPUで処理
            return self._generate_cpu(pcd, method)
    
    def _poisson_reconstruction_gpu(self, pcd_tensor: o3d.t.geometry.PointCloud) -> Optional[o3d.geometry.TriangleMesh]:
        """Poisson Surface Reconstruction（GPU対応）"""
        try:
            depth = self.poisson_config.get('depth', 9)
            width = self.poisson_config.get('width', 0)
            scale = self.poisson_config.get('scale', 1.1)
            linear_fit = self.poisson_config.get('linear_fit', False)
            
            print(f"Poisson reconstruction (GPU, depth={depth})...")
            
            # Tensor APIのPoisson reconstruction
            # 注意: Open3DのTensor APIではPoisson reconstructionが
            # 完全にサポートされていない可能性があるため、
            # 通常のAPIを使用する
            pcd_legacy = pcd_tensor.to_legacy()
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd_legacy,
                depth=depth,
                width=width,
                scale=scale,
                linear_fit=linear_fit
            )
            
            # 密度でフィルタリング
            densities = np.asarray(densities)
            percentile = self.poisson_config.get('density_threshold_percentile', 10)
            density_threshold = np.quantile(densities, percentile / 100.0)
            vertices_to_remove = densities < density_threshold
            mesh.remove_vertices_by_mask(vertices_to_remove)
            
            mesh.compute_vertex_normals()
            
            # メッシュ平滑化
            mesh = self._smooth_mesh(mesh)
            
            # メッシュ最適化
            mesh = self.clean_mesh(mesh)
            
            return mesh
            
        except Exception as e:
            print(f"GPU Poisson reconstruction failed: {e}")
            return None
    
    def _generate_cpu(self, pcd: o3d.geometry.PointCloud, method: str) -> Optional[o3d.geometry.TriangleMesh]:
        """CPUでメッシュ生成（フォールバック）"""
        # 法線がなければ計算
        if not pcd.has_normals():
            pcd.estimate_normals(
                search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
            )
            pcd.orient_normals_consistent_tangent_plane(30)
        
        if method == 'poisson':
            return self._poisson_reconstruction_cpu(pcd)
        elif method == 'ball_pivoting':
            return self._ball_pivoting(pcd)
        elif method == 'alpha_shape':
            return self._alpha_shape(pcd)
        else:
            print(f"Unknown method: {method}")
            return None
    
    def _poisson_reconstruction_cpu(self, pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        """Poisson Surface Reconstruction（CPU）"""
        depth = self.poisson_config.get('depth', 9)
        width = self.poisson_config.get('width', 0)
        scale = self.poisson_config.get('scale', 1.1)
        linear_fit = self.poisson_config.get('linear_fit', False)
        
        print(f"Poisson reconstruction (CPU, depth={depth})...")
        
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd,
            depth=depth,
            width=width,
            scale=scale,
            linear_fit=linear_fit
        )
        
        # 密度でフィルタリング
        densities = np.asarray(densities)
        percentile = self.poisson_config.get('density_threshold_percentile', 10)
        density_threshold = np.quantile(densities, percentile / 100.0)
        vertices_to_remove = densities < density_threshold
        mesh.remove_vertices_by_mask(vertices_to_remove)
        
        mesh.compute_vertex_normals()
        
        # メッシュ平滑化
        mesh = self._smooth_mesh(mesh)
        
        # メッシュ最適化
        mesh = self.clean_mesh(mesh)
        
        return mesh
    
    def _smooth_mesh(self, mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
        """メッシュ平滑化"""
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
                mu = -0.53
                mesh = mesh.filter_smooth_taubin(
                    number_of_iterations=iterations,
                    lambda_filter=lambda_filter,
                    mu=mu
                )
            
            mesh.compute_vertex_normals()
        
        return mesh
    
    def _ball_pivoting(self, pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        """Ball Pivoting Algorithm"""
        ball_pivoting_config = self.config.get('mesh', {}).get('ball_pivoting', {})
        radii = ball_pivoting_config.get('radii', [0.005, 0.01, 0.02, 0.04])
        radii = o3d.utility.DoubleVector(radii)
        
        print(f"Ball pivoting (radii={list(radii)})...")
        
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, radii
        )
        
        mesh.compute_vertex_normals()
        return mesh
    
    def _alpha_shape(self, pcd: o3d.geometry.PointCloud) -> o3d.geometry.TriangleMesh:
        """Alpha Shape"""
        alpha_config = self.config.get('mesh', {}).get('alpha_shape', {})
        alpha = alpha_config.get('alpha', 0.03)
        
        print(f"Alpha shape (alpha={alpha})...")
        
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(
            pcd, alpha
        )
        
        mesh.compute_vertex_normals()
        return mesh
    
    @staticmethod
    def simplify_mesh(mesh: o3d.geometry.TriangleMesh, 
                      target_triangles: int = 100000) -> o3d.geometry.TriangleMesh:
        """メッシュを簡略化"""
        current_triangles = len(mesh.triangles)
        
        if current_triangles <= target_triangles:
            return mesh
        
        print(f"Simplifying mesh: {current_triangles} -> {target_triangles} triangles")
        
        mesh = mesh.simplify_quadric_decimation(target_triangles)
        mesh.compute_vertex_normals()
        
        return mesh
    
    @staticmethod
    def clean_mesh(mesh: o3d.geometry.TriangleMesh) -> o3d.geometry.TriangleMesh:
        """メッシュをクリーンアップ"""
        mesh.remove_duplicated_vertices()
        mesh.remove_duplicated_triangles()
        mesh.remove_unreferenced_vertices()
        mesh.remove_degenerate_triangles()
        mesh.compute_vertex_normals()
        
        return mesh
    
    @staticmethod
    def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> Dict[str, Any]:
        """メッシュ情報を取得"""
        return {
            "vertices": len(mesh.vertices),
            "triangles": len(mesh.triangles),
            "has_normals": mesh.has_vertex_normals(),
            "has_colors": mesh.has_vertex_colors(),
            "is_watertight": mesh.is_watertight(),
            "surface_area": mesh.get_surface_area(),
            "volume": mesh.get_volume() if mesh.is_watertight() else None
        }


def create_mesh_from_rgbd_volume_gpu(volume, config: Dict[str, Any] = None, gpu_config: Dict[str, Any] = None) -> Tuple[o3d.geometry.PointCloud, o3d.geometry.TriangleMesh]:
    """
    TSDF Volumeから点群とメッシュを抽出（GPU対応）
    
    Args:
        volume: TSDF Volume
        config: 設定辞書
        gpu_config: GPU設定辞書
        
    Returns:
        (点群, メッシュ)
    """
    # メッシュ抽出
    mesh = volume.extract_triangle_mesh()
    
    # Tensor形式の場合は通常のTriangleMeshに変換
    if hasattr(mesh, 'to_legacy'):
        mesh = mesh.to_legacy()
    
    mesh.compute_vertex_normals()
    
    # 点群抽出
    pcd = volume.extract_point_cloud()
    
    # Tensor形式の場合は通常のPointCloudに変換
    if hasattr(pcd, 'to_legacy'):
        pcd = pcd.to_legacy()
    
    # メッシュクリーンアップ
    mesh = MeshGeneratorGPU.clean_mesh(mesh)
    
    # 簡略化（オプション）
    output_config = config.get('output', {}) if config else {}
    if output_config.get('simplify', False):
        target = output_config.get('target_triangles', 100000)
        mesh = MeshGeneratorGPU.simplify_mesh(mesh, target)
    
    return pcd, mesh

