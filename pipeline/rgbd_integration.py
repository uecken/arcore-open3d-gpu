"""
RGB-D Integration Pipeline
Open3D TSDF Volume Integration
"""

import numpy as np
import cv2
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import open3d as o3d

from utils.arcore_parser import ARCoreDataParser, Frame, CameraIntrinsics
from utils.transforms import arcore_to_open3d_pose


class RGBDIntegration:
    """
    RGB-D画像をTSDF Volumeに統合して3D再構成
    """
    
    def __init__(self, config: Dict[str, Any] = None, gpu_config: Dict[str, Any] = None):
        """
        Args:
            config: 設定辞書
            gpu_config: GPU設定辞書（config.yamlのgpuセクション）
        """
        self.config = config or {}
        self.gpu_config = gpu_config or {}
        
        # TSDF設定
        tsdf_config = self.config.get('tsdf', {})
        self.voxel_length = tsdf_config.get('voxel_length', 0.005)  # 5mm
        self.sdf_trunc = tsdf_config.get('sdf_trunc', 0.04)  # 4cm
        
        # Depth設定
        depth_config = self.config.get('depth', {})
        self.depth_scale = depth_config.get('scale', 1000.0)
        self.depth_trunc = depth_config.get('trunc', 3.0)
        self.min_depth = depth_config.get('min_depth', 0.1)
        
        # GPU設定
        self.use_gpu = self.gpu_config.get('enabled', True) and self.gpu_config.get('use_cuda', True)
        self.o3d_device = None
        
        # Open3DのGPU対応を確認
        self._check_open3d_gpu_support()
        
        self.volume = None
        self.intrinsic = None
    
    def _check_open3d_gpu_support(self):
        """Open3DのGPU対応を確認"""
        try:
            # Open3D 0.19以降でo3d.core.Deviceが利用可能
            if hasattr(o3d, 'core') and hasattr(o3d.core, 'Device'):
                if self.use_gpu:
                    try:
                        # CUDAデバイスを確認
                        devices = o3d.core.Device.get_available_devices()
                        cuda_devices = [d for d in devices if 'CUDA' in str(d)]
                        if cuda_devices:
                            device_id = self.gpu_config.get('device_id', 0)
                            self.o3d_device = o3d.core.Device(f"CUDA:{device_id}")
                            print(f"Open3D GPU device: {self.o3d_device}")
                        else:
                            print("Warning: Open3D CUDA device not found, using CPU")
                            self.o3d_device = o3d.core.Device("CPU:0")
                            self.use_gpu = False
                    except Exception as e:
                        print(f"Warning: Failed to initialize Open3D GPU device: {e}")
                        self.o3d_device = o3d.core.Device("CPU:0")
                        self.use_gpu = False
                else:
                    self.o3d_device = o3d.core.Device("CPU:0")
            else:
                print("Warning: Open3D GPU support (o3d.core.Device) not available")
                print("Note: ScalableTSDFVolume runs on CPU by default")
                self.use_gpu = False
        except Exception as e:
            print(f"Warning: Error checking Open3D GPU support: {e}")
            self.use_gpu = False
    
    def load_depth_image(self, depth_path: Path, expected_width: int = None, expected_height: int = None) -> Optional[o3d.geometry.Image]:
        """
        ARCore深度画像を読み込む（.raw形式とPNG形式の両方に対応）
        
        Args:
            depth_path: 深度画像のパス
            expected_width: 期待される幅（.rawファイルの場合）
            expected_height: 期待される高さ（.rawファイルの場合）
            
        Returns:
            Open3D Imageオブジェクト、またはNone
        """
        if not depth_path.exists():
            return None
        
        try:
            # .rawファイルの場合
            if depth_path.suffix.lower() == '.raw':
                # ARCoreの.rawファイルは16bit深度データ（ミリメートル単位）
                # ファイルサイズから画像サイズを推定
                file_size = depth_path.stat().st_size
                
                # 16bit = 2 bytes per pixel
                total_pixels = file_size // 2
                
                # ファイルサイズから実際の解像度を計算（優先）
                # ARCore深度画像は正方形の可能性が高い
                import math
                sqrt_pixels = int(math.sqrt(total_pixels))
                
                # 正方形として試す
                if sqrt_pixels * sqrt_pixels == total_pixels:
                    # 完全な正方形
                    actual_width = sqrt_pixels
                    actual_height = sqrt_pixels
                else:
                    # 正方形でない場合、一般的なARCore深度解像度を試す
                    common_resolutions = [
                        (320, 240),   # 76800 pixels
                        (640, 480),   # 307200 pixels
                        (256, 192),   # 49152 pixels
                        (160, 120),   # 19200 pixels
                        (120, 120),   # 14400 pixels (正方形)
                        (128, 96),    # 12288 pixels
                        (96, 96),     # 9216 pixels (正方形)
                    ]
                    
                    # 最も近い解像度を選択
                    best_match = None
                    min_diff = float('inf')
                    for w, h in common_resolutions:
                        expected_pixels = w * h
                        diff = abs(total_pixels - expected_pixels)
                        if diff < min_diff:
                            min_diff = diff
                            best_match = (w, h)
                    
                    if best_match and min_diff < total_pixels * 0.1:  # 10%以内の誤差
                        actual_width, actual_height = best_match
                    else:
                        # デフォルトとして最も近い正方形を使用
                        actual_width = sqrt_pixels
                        actual_height = sqrt_pixels
                        print(f"Warning: Depth file size ({total_pixels} pixels) doesn't match common resolutions. Using {actual_width}x{actual_height}")
                
                # 実際のファイルサイズから計算した解像度を優先
                expected_width = actual_width
                expected_height = actual_height
                
                # バイナリデータを読み込み
                with open(depth_path, 'rb') as f:
                    raw_data = f.read()
                
                # 16bit unsigned integerとして解釈
                depth_array = np.frombuffer(raw_data, dtype=np.uint16)
                
                # 形状を変更
                if len(depth_array) == expected_width * expected_height:
                    depth_array = depth_array.reshape((expected_height, expected_width))
                else:
                    # サイズが合わない場合、可能な限り再構築
                    actual_pixels = len(depth_array)
                    if actual_pixels >= expected_width * expected_height:
                        depth_array = depth_array[:expected_width * expected_height].reshape((expected_height, expected_width))
                    else:
                        print(f"Error: Depth file has {actual_pixels} pixels, expected {expected_width * expected_height}")
                        return None
                
                # ミリメートル単位の深度値をメートル単位に変換
                # ARCoreはmm単位で保存しているため、1000で割る
                # ただし、Open3Dのcreate_from_color_and_depthではdepth_scaleを使用するため、
                # ここではuint16のまま保持（depth_scale=1000.0で処理）
                depth_image = o3d.geometry.Image(depth_array)
                return depth_image
            
            # PNG/JPEGファイルの場合（通常の画像読み込み）
            else:
                # OpenCVで16bit深度画像として読み込み
                depth_cv = cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)
                
                if depth_cv is None:
                    print(f"Failed to read depth image: {depth_path}")
                    return None
                
                # グレースケールに変換（3チャンネルの場合）
                if len(depth_cv.shape) == 3:
                    depth_cv = cv2.cvtColor(depth_cv, cv2.COLOR_BGR2GRAY)
                
                # uint16として扱う（ARCoreはmm単位）
                if depth_cv.dtype != np.uint16:
                    # 8bitの場合は16bitに変換（スケールを保持）
                    if depth_cv.dtype == np.uint8:
                        depth_cv = depth_cv.astype(np.uint16) * 256
                    else:
                        depth_cv = depth_cv.astype(np.uint16)
                
                depth_image = o3d.geometry.Image(depth_cv)
                return depth_image
                
        except Exception as e:
            print(f"Error loading depth image {depth_path}: {e}")
            return None
    
    def create_volume(self) -> o3d.pipelines.integration.ScalableTSDFVolume:
        """TSDF Volumeを作成"""
        # 注意: ScalableTSDFVolumeは現在のOpen3Dバージョンでは
        # GPUデバイスパラメータをサポートしていないため、CPUで実行されます
        # GPU対応には、Open3Dの新しいTensor APIを使用する必要があります
        self.volume = o3d.pipelines.integration.ScalableTSDFVolume(
            voxel_length=self.voxel_length,
            sdf_trunc=self.sdf_trunc,
            color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
        )
        
        if self.use_gpu and self.o3d_device:
            print(f"Note: TSDF Volume created (GPU device available: {self.o3d_device}, but ScalableTSDFVolume runs on CPU)")
        else:
            print("Note: TSDF Volume created (running on CPU)")
        
        return self.volume
    
    def set_intrinsics(self, intrinsics: CameraIntrinsics):
        """カメラ内部パラメータを設定"""
        self.intrinsic = o3d.camera.PinholeCameraIntrinsic(
            intrinsics.width,
            intrinsics.height,
            intrinsics.fx,
            intrinsics.fy,
            intrinsics.cx,
            intrinsics.cy
        )
    
    def integrate_frame(self, 
                        color_path: Path, 
                        depth_path: Path, 
                        pose: np.ndarray) -> bool:
        """
        1フレームをVolumeに統合
        
        Args:
            color_path: カラー画像パス
            depth_path: Depth画像パス
            pose: 4x4カメラポーズ行列
            
        Returns:
            成功したかどうか
        """
        if self.volume is None:
            self.create_volume()
        
        if self.intrinsic is None:
            raise ValueError("Camera intrinsics not set")
        
        try:
            # 画像読み込み
            color = o3d.io.read_image(str(color_path))
            
            # 深度画像読み込み（.raw形式対応）
            color_np = np.asarray(color)
            img_h, img_w = color_np.shape[:2]
            
            depth = self.load_depth_image(depth_path, expected_width=img_w, expected_height=img_h)
            if depth is None:
                print(f"Failed to load depth image: {depth_path}")
                return False
            
            # サイズ確認・リサイズ（ARCore Depth は低解像度の場合がある）
            depth_np = np.asarray(depth)
            
            if color_np.shape[:2] != depth_np.shape[:2]:
                # Depth を RGB サイズにリサイズ
                target_h, target_w = color_np.shape[:2]
                depth_resized = cv2.resize(depth_np, (target_w, target_h), 
                                           interpolation=cv2.INTER_NEAREST)
                depth = o3d.geometry.Image(depth_resized)
                depth_np = depth_resized
            
            # 画像サイズに基づいてintrinsicを調整（Portrait/Landscape対応）
            img_h, img_w = color_np.shape[:2]
            intrinsic_w = self.intrinsic.width
            intrinsic_h = self.intrinsic.height
            
            # 画像とintrinsicの向きが異なる場合（縦横が逆）
            if (img_w == intrinsic_h and img_h == intrinsic_w):
                # intrinsicの幅と高さを入れ替え、cx/cyも入れ替え
                intrinsic_params = self.intrinsic.intrinsic_matrix
                fx = intrinsic_params[0, 0]
                fy = intrinsic_params[1, 1]
                cx = intrinsic_params[0, 2]
                cy = intrinsic_params[1, 2]
                
                # Portrait用に調整: 幅と高さを交換、fx/fyを交換、cx/cyを交換
                frame_intrinsic = o3d.camera.PinholeCameraIntrinsic(
                    img_w, img_h,  # 実際の画像サイズ
                    fy, fx,        # fxとfyを交換
                    cy, cx         # cxとcyを交換
                )
            elif img_w != intrinsic_w or img_h != intrinsic_h:
                # サイズが異なる場合はスケーリング
                scale_x = img_w / intrinsic_w
                scale_y = img_h / intrinsic_h
                intrinsic_params = self.intrinsic.intrinsic_matrix
                fx = intrinsic_params[0, 0] * scale_x
                fy = intrinsic_params[1, 1] * scale_y
                cx = intrinsic_params[0, 2] * scale_x
                cy = intrinsic_params[1, 2] * scale_y
                
                frame_intrinsic = o3d.camera.PinholeCameraIntrinsic(
                    img_w, img_h, fx, fy, cx, cy
                )
            else:
                frame_intrinsic = self.intrinsic
            
            # 深度画像のノイズ除去（オプション）
            depth_np_filtered = depth_np.copy()
            depth_config = self.config.get('depth', {})
            
            if depth_config.get('filter_noise', False):
                # 統計的外れ値除去（深度値の異常値を除去）
                depth_flat = depth_np_filtered.flatten()
                valid_mask = (depth_flat > 0) & (depth_flat < self.depth_trunc * self.depth_scale)
                valid_depths = depth_flat[valid_mask]
                
                if len(valid_depths) > 0:
                    mean_depth = np.mean(valid_depths)
                    std_depth = np.std(valid_depths)
                    threshold = mean_depth + 3 * std_depth  # 3σルール
                    
                    # 異常値を0に設定（無効化）
                    depth_np_filtered[depth_np_filtered > threshold] = 0
            
            if depth_config.get('bilateral_filter', False):
                # Bilateral filter（エッジを保持しながらノイズ除去）
                # OpenCVのbilateralFilterはuint8またはfloat32のみサポート
                try:
                    d = depth_config.get('bilateral_d', 5)
                    sigma_color = depth_config.get('bilateral_sigma_color', 50.0)
                    sigma_space = depth_config.get('bilateral_sigma_space', 50.0)
                    
                    # uint16をfloat32に変換（0-65535の範囲を0.0-1.0に正規化）
                    depth_max = depth_np_filtered.max()
                    if depth_max > 0:
                        depth_float = depth_np_filtered.astype(np.float32) / depth_max
                        
                        # Bilateral filterを適用
                        depth_filtered_float = cv2.bilateralFilter(
                            depth_float, d, sigma_color, sigma_space
                        )
                        
                        # float32をuint16に戻す
                        depth_np_filtered = (depth_filtered_float * depth_max).astype(np.uint16)
                    else:
                        # 深度データがすべて0の場合はスキップ
                        pass
                except Exception as e:
                    print(f"Bilateral filter failed: {e}, using original depth")
                    # エラー時は元の深度画像を使用
            
            # フィルタリング後の深度画像を使用
            depth_filtered_img = o3d.geometry.Image(depth_np_filtered)
            
            # RGBD画像作成
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth_filtered_img,
                depth_scale=self.depth_scale,
                depth_trunc=self.depth_trunc,
                convert_rgb_to_intensity=False
            )
            
            # Open3D座標系に変換
            o3d_pose = arcore_to_open3d_pose(pose)
            
            # 統合（Open3Dはカメラ→ワールドの逆行列を期待）
            self.volume.integrate(rgbd, frame_intrinsic, np.linalg.inv(o3d_pose))
            
            return True
            
        except Exception as e:
            print(f"Frame integration error: {e}")
            return False
    
    def process_session(self, 
                        parser: ARCoreDataParser,
                        progress_callback: Callable[[int, str], None] = None) -> bool:
        """
        セッション全体を処理
        
        Args:
            parser: ARCoreデータパーサー
            progress_callback: 進捗コールバック (progress: int, message: str)
            
        Returns:
            成功したかどうか
        """
        if parser.intrinsics is None:
            print("No camera intrinsics")
            return False
        
        self.set_intrinsics(parser.intrinsics)
        self.create_volume()
        
        # Depthがあるフレームを取得
        frames = parser.get_frames_with_depth()
        
        if not frames:
            print("No frames with depth data")
            return False
        
        total = len(frames)
        success_count = 0
        
        for i, frame in enumerate(frames):
            if frame.pose is None:
                continue
            
            pose_matrix = frame.pose.to_matrix()
            
            success = self.integrate_frame(
                frame.image_path,
                frame.depth_path,
                pose_matrix
            )
            
            if success:
                success_count += 1
            
            if progress_callback:
                progress = int((i + 1) / total * 100)
                progress_callback(progress, f"Integrated {i + 1}/{total} frames")
        
        print(f"Integrated {success_count}/{total} frames")
        return success_count > 0
    
    def extract_point_cloud(self) -> Optional[o3d.geometry.PointCloud]:
        """点群を抽出"""
        if self.volume is None:
            return None
        
        pcd = self.volume.extract_point_cloud()
        
        # 点群の後処理
        pcd_config = self.config.get('pointcloud', {})
        
        # 統計的外れ値除去
        if pcd_config.get('remove_outliers', True) and len(pcd.points) > 0:
            nb_neighbors = pcd_config.get('nb_neighbors', 20)
            std_ratio = pcd_config.get('std_ratio', 2.0)
            pcd, _ = pcd.remove_statistical_outlier(
                nb_neighbors=nb_neighbors,
                std_ratio=std_ratio
            )
        
        # 半径ベースの外れ値除去
        if pcd_config.get('radius_outlier_removal', False) and len(pcd.points) > 0:
            radius = pcd_config.get('radius', 0.05)
            min_neighbors = pcd_config.get('min_neighbors', 10)
            pcd, _ = pcd.remove_radius_outlier(
                nb_points=min_neighbors,
                radius=radius
            )
        
        # 平滑化（法線の再計算）
        if pcd_config.get('smooth', False) and len(pcd.points) > 0:
            iterations = pcd_config.get('smooth_iterations', 1)
            for _ in range(iterations):
                # 法線を再計算することで平滑化効果
                pcd.estimate_normals(
                    search_param=o3d.geometry.KDTreeSearchParamHybrid(
                        radius=0.1, max_nn=30
                    )
                )
                pcd.orient_normals_consistent_tangent_plane(30)
        
        return pcd
    
    def extract_mesh(self) -> Optional[o3d.geometry.TriangleMesh]:
        """メッシュを抽出"""
        if self.volume is None:
            return None
        
        mesh = self.volume.extract_triangle_mesh()
        mesh.compute_vertex_normals()
        return mesh


class PointCloudFusion:
    """
    点群の直接融合（Depthなし、ARCore点群使用）
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        pcd_config = self.config.get('pointcloud', {})
        self.voxel_size = pcd_config.get('voxel_down_size', 0.01)
        self.remove_outliers = pcd_config.get('remove_outliers', True)
        self.nb_neighbors = pcd_config.get('nb_neighbors', 20)
        self.std_ratio = pcd_config.get('std_ratio', 2.0)
        
        self.combined_pcd = o3d.geometry.PointCloud()
    
    def add_point_cloud(self, 
                        pcd: o3d.geometry.PointCloud, 
                        pose: np.ndarray) -> None:
        """
        点群をワールド座標に変換して追加
        
        Args:
            pcd: 点群
            pose: 4x4変換行列
        """
        transformed = pcd.transform(pose)
        self.combined_pcd += transformed
    
    def add_points(self, 
                   points: np.ndarray, 
                   colors: Optional[np.ndarray],
                   pose: np.ndarray) -> None:
        """
        点群データを追加
        
        Args:
            points: Nx3の点座標
            colors: Nx3の色（0-1）
            pose: 4x4変換行列
        """
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        if colors is not None:
            pcd.colors = o3d.utility.Vector3dVector(colors)
        
        self.add_point_cloud(pcd, pose)
    
    def finalize(self) -> o3d.geometry.PointCloud:
        """
        点群を最終処理（ダウンサンプリング、外れ値除去）
        
        Returns:
            処理済み点群
        """
        if len(self.combined_pcd.points) == 0:
            return self.combined_pcd
        
        # Voxelダウンサンプリング
        pcd = self.combined_pcd.voxel_down_sample(voxel_size=self.voxel_size)
        
        # 外れ値除去
        if self.remove_outliers and len(pcd.points) > self.nb_neighbors:
            pcd, _ = pcd.remove_statistical_outlier(
                nb_neighbors=self.nb_neighbors,
                std_ratio=self.std_ratio
            )
        
        return pcd

