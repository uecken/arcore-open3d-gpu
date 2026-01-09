"""
RGB-D Integration Pipeline (GPU対応版)
Open3D Tensor APIを使用したTSDF Volume Integration
"""

import numpy as np
import cv2
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
import open3d as o3d

from utils.arcore_parser import ARCoreDataParser, Frame, CameraIntrinsics
from utils.transforms import arcore_to_open3d_pose


class RGBDIntegrationGPU:
    """
    RGB-D画像をTSDF Volumeに統合して3D再構成（GPU対応版）
    Open3D Tensor APIを使用
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
        
        # Open3DのGPU対応を確認・初期化
        self._initialize_device()
        
        self.volume = None
        self.intrinsic = None
        self.is_tensor_volume = False  # Tensor APIのTSDFVolumeかどうかのフラグ
        
    def _initialize_device(self):
        """Open3DのGPUデバイスを初期化"""
        try:
            # Open3D 0.19以降でo3d.core.Deviceが利用可能
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
                                    print(f"✓ Open3D GPU device initialized: {self.o3d_device}")
                                else:
                                    print(f"⚠ Warning: Device type is {device_type}, not CUDA. Using CPU.")
                                    self.o3d_device = o3d.core.Device("CPU:0")
                                    self.use_gpu = False
                            except Exception as e:
                                print(f"⚠ Warning: Failed to create Open3D CUDA device: {e}")
                                print("  Note: Open3D may not have CUDA support compiled. Using CPU.")
                                self.o3d_device = o3d.core.Device("CPU:0")
                                self.use_gpu = False
                        else:
                            print("⚠ Warning: PyTorch CUDA not available. Using CPU.")
                            self.o3d_device = o3d.core.Device("CPU:0")
                            self.use_gpu = False
                    except ImportError:
                        print("⚠ Warning: PyTorch not available. Using CPU.")
                        self.o3d_device = o3d.core.Device("CPU:0")
                        self.use_gpu = False
                else:
                    self.o3d_device = o3d.core.Device("CPU:0")
                    print("ℹ Using CPU device (GPU disabled in config)")
            else:
                print("⚠ Warning: Open3D GPU support (o3d.core.Device) not available")
                print("   Falling back to CPU. Please install Open3D with CUDA support.")
                self.o3d_device = o3d.core.Device("CPU:0")
                self.use_gpu = False
        except Exception as e:
            print(f"⚠ Warning: Error initializing Open3D device: {e}")
            self.o3d_device = o3d.core.Device("CPU:0")
            self.use_gpu = False
    
    def load_depth_image(self, depth_path: Path, expected_width: int = None, expected_height: int = None) -> Optional[o3d.geometry.Image]:
        """
        ARCore深度画像を読み込む（.raw形式とPNG形式の両方に対応）
        元のコードと同じ実装
        
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
    
    def load_depth_image_tensor(self, depth_path: Path, expected_width: int = None, expected_height: int = None) -> Optional[o3d.t.geometry.Image]:
        """
        ARCore深度画像をTensor形式で読み込む
        
        Args:
            depth_path: 深度画像のパス
            expected_width: 期待される幅（.rawファイルの場合）
            expected_height: 期待される高さ（.rawファイルの場合）
            
        Returns:
            Open3D Tensor Imageオブジェクト、またはNone
        """
        if not depth_path.exists():
            return None
        
        try:
            # まず通常のImageとして読み込み
            depth_array = None
            
            # .rawファイルの場合
            if depth_path.suffix.lower() == '.raw':
                file_size = depth_path.stat().st_size
                total_pixels = file_size // 2
                
                import math
                sqrt_pixels = int(math.sqrt(total_pixels))
                
                if sqrt_pixels * sqrt_pixels == total_pixels:
                    actual_width = sqrt_pixels
                    actual_height = sqrt_pixels
                else:
                    common_resolutions = [
                        (320, 240), (640, 480), (256, 192),
                        (160, 120), (120, 120), (128, 96), (96, 96),
                    ]
                    best_match = None
                    min_diff = float('inf')
                    for w, h in common_resolutions:
                        expected_pixels = w * h
                        diff = abs(total_pixels - expected_pixels)
                        if diff < min_diff:
                            min_diff = diff
                            best_match = (w, h)
                    
                    if best_match and min_diff < total_pixels * 0.1:
                        actual_width, actual_height = best_match
                    else:
                        actual_width = sqrt_pixels
                        actual_height = sqrt_pixels
                
                expected_width = actual_width
                expected_height = actual_height
                
                with open(depth_path, 'rb') as f:
                    raw_data = f.read()
                
                depth_array = np.frombuffer(raw_data, dtype=np.uint16)
                
                if len(depth_array) == expected_width * expected_height:
                    depth_array = depth_array.reshape((expected_height, expected_width))
                else:
                    actual_pixels = len(depth_array)
                    if actual_pixels >= expected_width * expected_height:
                        depth_array = depth_array[:expected_width * expected_height].reshape((expected_height, expected_width))
                    else:
                        print(f"Error: Depth file has {actual_pixels} pixels, expected {expected_width * expected_height}")
                        return None
            else:
                # PNG/JPEGファイルの場合
                depth_cv = cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)
                if depth_cv is None:
                    print(f"Failed to read depth image: {depth_path}")
                    return None
                
                if len(depth_cv.shape) == 3:
                    depth_cv = cv2.cvtColor(depth_cv, cv2.COLOR_BGR2GRAY)
                
                if depth_cv.dtype != np.uint16:
                    if depth_cv.dtype == np.uint8:
                        depth_cv = depth_cv.astype(np.uint16) * 256
                    else:
                        depth_cv = depth_cv.astype(np.uint16)
                
                depth_array = depth_cv
            
            # NumPy配列をTensor Imageに変換
            # Tensor APIを使用
            if hasattr(o3d, 't') and hasattr(o3d.t, 'geometry'):
                # Open3D Tensor APIが利用可能
                depth_tensor = o3d.core.Tensor(depth_array, device=self.o3d_device)
                depth_image = o3d.t.geometry.Image(depth_tensor)
                return depth_image
            else:
                # フォールバック: 通常のImageを使用
                depth_image = o3d.geometry.Image(depth_array)
                # Tensor Imageに変換を試みる
                try:
                    depth_tensor = o3d.core.Tensor(np.asarray(depth_image), device=self.o3d_device)
                    return o3d.t.geometry.Image(depth_tensor)
                except:
                    return None
                
        except Exception as e:
            print(f"Error loading depth image {depth_path}: {e}")
            return None
    
    def create_volume(self):
        """TSDF Volumeを作成（GPU対応、Tensor APIを優先的に使用）"""
        try:
            print(f"ℹ Creating TSDF Volume (device: {self.o3d_device})")
            print(f"  Voxel length: {self.voxel_length}m ({self.voxel_length*1000:.1f}mm)")
            
            # メモリ使用量の警告
            if self.voxel_length < 0.004:
                print("  ⚠ Warning: Very small voxel_length may cause high memory usage!")
                print("    Consider using voxel_length >= 0.005 (5mm) for better memory efficiency.")
            
            # Tensor APIのTSDFVolumeを試みる（GPU対応）
            if self.use_gpu:
                try:
                    # Tensor APIのTSDFVolumeが存在するか確認（安全な方法）
                    if hasattr(o3d, 't'):
                        if hasattr(o3d.t, 'pipelines'):
                            if hasattr(o3d.t.pipelines, 'slam'):
                                if hasattr(o3d.t.pipelines.slam, 'TSDFVolume'):
                                    # Tensor APIのTSDFVolumeを使用（GPU対応）
                                    print("  Attempting to use Tensor API TSDFVolume (GPU)...")
                                    self.volume = o3d.t.pipelines.slam.TSDFVolume(
                                        voxel_length=self.voxel_length,
                                        sdf_trunc=self.sdf_trunc,
                                        color_type=o3d.core.TensorDtype.UInt8,
                                        device=self.o3d_device
                                    )
                                    self.is_tensor_volume = True
                                    print(f"  ✓ Tensor API TSDFVolume created on {self.o3d_device} (GPU)")
                                    return self.volume
                    print("  ⚠ Tensor API TSDFVolume not available in this Open3D version")
                except (AttributeError, Exception) as e:
                    print(f"  ⚠ Tensor API TSDFVolume failed: {e}")
                    print("  Falling back to ScalableTSDFVolume (CPU)...")
            
            # フォールバック: 従来のScalableTSDFVolumeを使用（CPU）
            print("  Note: Using ScalableTSDFVolume (CPU). Tensor API TSDFVolume is experimental.")
            self.volume = o3d.pipelines.integration.ScalableTSDFVolume(
                voxel_length=self.voxel_length,
                sdf_trunc=self.sdf_trunc,
                color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
            )
            self.is_tensor_volume = False
            return self.volume
            
        except Exception as e:
            print(f"Error creating TSDF volume: {e}")
            raise
    
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
    
    def _image_to_tensor(self, image: o3d.geometry.Image) -> Optional[o3d.t.geometry.Image]:
        """通常のImageをTensor Imageに変換"""
        try:
            if hasattr(o3d, 't') and hasattr(o3d.t, 'geometry'):
                img_array = np.asarray(image)
                img_tensor = o3d.core.Tensor(img_array, device=self.o3d_device)
                return o3d.t.geometry.Image(img_tensor)
            return None
        except Exception as e:
            print(f"Error converting image to tensor: {e}")
            return None
    
    def integrate_frame(self, 
                        color_path: Path, 
                        depth_path: Path, 
                        pose: np.ndarray) -> bool:
        """
        1フレームをVolumeに統合（GPU対応）
        
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
            color_np = np.asarray(color)
            img_h, img_w = color_np.shape[:2]
            
            # 深度画像読み込み（通常のImage形式で読み込み、後でTensorに変換）
            depth = self.load_depth_image(depth_path, expected_width=img_w, expected_height=img_h)
            if depth is None:
                print(f"Failed to load depth image: {depth_path}")
                return False
            
            # サイズ確認・リサイズ（元のコードと同じ処理）
            depth_np = np.asarray(depth)
            
            if color_np.shape[:2] != depth_np.shape[:2]:
                # Depth を RGB サイズにリサイズ
                target_h, target_w = color_np.shape[:2]
                depth_resized = cv2.resize(depth_np, (target_w, target_h), 
                                           interpolation=cv2.INTER_NEAREST)
                depth = o3d.geometry.Image(depth_resized)
                depth_np = depth_resized
            
            # 画像サイズに基づいてintrinsicを調整（Portrait/Landscape対応）
            frame_intrinsic = self._adjust_intrinsic(img_w, img_h)
            
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
                except Exception as e:
                    print(f"Bilateral filter failed: {e}, using original depth")
                    # エラー時は元の深度画像を使用
            
            # Open3D座標系に変換
            o3d_pose = arcore_to_open3d_pose(pose)
            
            # Tensor APIのTSDFVolumeを使用している場合
            if self.is_tensor_volume and hasattr(self.volume, 'integrate'):
                # Tensor APIが利用可能か安全に確認
                try:
                    tensor_available = hasattr(o3d, 't') and hasattr(o3d.t, 'geometry')
                except (AttributeError, Exception):
                    tensor_available = False
                
                if tensor_available:
                    # Tensor APIを使用して統合（GPU上で実行）
                    try:
                        # カラー画像をTensor形式に変換
                        color_array = np.asarray(color)
                        if len(color_array.shape) == 2:
                            # グレースケールの場合はRGBに変換
                            color_array = np.stack([color_array, color_array, color_array], axis=-1)
                        color_tensor = o3d.core.Tensor(color_array, device=self.o3d_device)
                        color_img = o3d.t.geometry.Image(color_tensor)
                        
                        # 深度画像をTensor形式に変換（メートル単位）
                        depth_array = depth_np_filtered.astype(np.float32) / self.depth_scale
                        depth_tensor = o3d.core.Tensor(depth_array, device=self.o3d_device)
                        depth_img = o3d.t.geometry.Image(depth_tensor)
                        
                        # RGBD画像を作成（Tensor形式）
                        rgbd_tensor = o3d.t.geometry.RGBDImage(color_img, depth_img)
                        
                        # カメラ内部パラメータをTensor形式に変換
                        intrinsic_matrix = frame_intrinsic.intrinsic_matrix
                        intrinsic_tensor = o3d.core.Tensor(intrinsic_matrix, device=self.o3d_device)
                        
                        # ポーズをTensor形式に変換（カメラ→ワールドの逆行列）
                        pose_inv = np.linalg.inv(o3d_pose)
                        pose_tensor = o3d.core.Tensor(pose_inv, device=self.o3d_device)
                        
                        # Volumeに統合（Tensor API、GPU上で実行）
                        self.volume.integrate(rgbd_tensor, intrinsic_tensor, pose_tensor, self.depth_scale, self.depth_trunc)
                        return True
                    except Exception as e:
                        print(f"Tensor API integration failed: {e}, falling back to legacy API")
                        import traceback
                        traceback.print_exc()
                        # フォールバック: 通常のAPIを使用
                else:
                    # Tensor APIが利用できない場合は通常のAPIを使用
                    pass
            
            # 通常のAPIを使用（ScalableTSDFVolumeの場合）
            depth_filtered_img = o3d.geometry.Image(depth_np_filtered)
            
            # RGBD画像作成
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth_filtered_img,
                depth_scale=self.depth_scale,
                depth_trunc=self.depth_trunc,
                convert_rgb_to_intensity=False
            )
            
            # 統合（Open3Dはカメラ→ワールドの逆行列を期待）
            self.volume.integrate(rgbd, frame_intrinsic, np.linalg.inv(o3d_pose))
            return True
            
        except Exception as e:
            print(f"Frame integration error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _adjust_intrinsic(self, img_w: int, img_h: int) -> o3d.camera.PinholeCameraIntrinsic:
        """画像サイズに基づいてintrinsicを調整"""
        intrinsic_w = self.intrinsic.width
        intrinsic_h = self.intrinsic.height
        
        if (img_w == intrinsic_h and img_h == intrinsic_w):
            intrinsic_params = self.intrinsic.intrinsic_matrix
            fx = intrinsic_params[0, 0]
            fy = intrinsic_params[1, 1]
            cx = intrinsic_params[0, 2]
            cy = intrinsic_params[1, 2]
            
            frame_intrinsic = o3d.camera.PinholeCameraIntrinsic(
                img_w, img_h, fy, fx, cy, cx
            )
        elif img_w != intrinsic_w or img_h != intrinsic_h:
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
        
        return frame_intrinsic
    
    def process_session(self, 
                        parser: ARCoreDataParser,
                        progress_callback: Callable[[int, str], None] = None,
                        force_depth_estimation: bool = False) -> bool:
        """
        セッション全体を処理（GPU対応、深度推定の強制使用オプション付き）
        
        Args:
            parser: ARCoreデータパーサー
            progress_callback: 進捗コールバック (progress: int, message: str)
            force_depth_estimation: 深度推定を強制的に使用するか（GPU使用のため）
            
        Returns:
            成功したかどうか
        """
        if parser.intrinsics is None:
            print("No camera intrinsics")
            return False
        
        self.set_intrinsics(parser.intrinsics)
        self.create_volume()
        
        # 深度推定の強制使用（GPU使用のため）
        depth_estimator = None
        if force_depth_estimation or not parser.has_depth_data():
            try:
                from pipeline.depth_estimation import MiDaSDepthEstimator
                depth_config = self.config.get('depth_estimation', {})
                depth_estimator = MiDaSDepthEstimator(
                    model_name=depth_config.get('model', 'DPT_Large'),
                    device=depth_config.get('device', 'cuda'),
                    gpu_config=self.gpu_config
                )
                print(f"✓ Depth estimator initialized (GPU: {depth_estimator.device})")
            except Exception as e:
                print(f"⚠ Failed to initialize depth estimator: {e}")
                if force_depth_estimation:
                    print("  Continuing without depth estimation...")
        
        # Depthがあるフレームを取得（深度推定を使用する場合は全フレーム）
        if depth_estimator is not None:
            frames = parser.get_frames_with_pose()
        else:
            frames = parser.get_frames_with_depth()
        
        if not frames:
            print("No frames available")
            return False
        
        total = len(frames)
        success_count = 0
        
        for i, frame in enumerate(frames):
            if frame.pose is None:
                continue
            
            pose_matrix = frame.pose.to_matrix()
            
            # 深度推定を使用する場合
            if depth_estimator is not None:
                try:
                    # カラー画像から深度を推定（GPU）
                    color_img = cv2.imread(str(frame.image_path))
                    if color_img is not None:
                        # MiDaSの深度推定: scaleはメートル単位への変換係数
                        # 部屋スキャンの場合、scale=10.0で0.2m-10mの範囲をカバー
                        midas_scale = 10.0  # depth_scale(1000.0)ではなく、MiDaS用のスケール
                        depth_map = depth_estimator.estimate_depth_metric(
                            color_img,
                            scale=midas_scale,
                            shift=0.0
                        )
                        # 深度マップをuint16形式に変換（メートル→ミリメートル）
                        # depth_mapはメートル単位なので、1000倍でミリメートルに変換
                        depth_map_uint16 = (depth_map * 1000.0).astype(np.uint16)
                        depth_img = o3d.geometry.Image(depth_map_uint16)
                        color = o3d.io.read_image(str(frame.image_path))
                        success = self.integrate_frame_with_images(color, depth_img, pose_matrix)
                    else:
                        continue
                except Exception as e:
                    print(f"Depth estimation failed for {frame.image_path}: {e}")
                    continue
            else:
                # 通常の深度画像を使用
                if frame.depth_path is None or not frame.depth_path.exists():
                    continue
                success = self.integrate_frame(
                    frame.image_path,
                    frame.depth_path,
                    pose_matrix
                )
            
            if success:
                success_count += 1
            
            if progress_callback:
                progress = int((i + 1) / total * 100)
                gpu_status = "GPU" if self.use_gpu else "CPU"
                depth_status = "estimated" if depth_estimator is not None else "original"
                progress_callback(progress, f"Integrated {i + 1}/{total} frames ({gpu_status}, depth: {depth_status})")
        
        print(f"Integrated {success_count}/{total} frames")
        return success_count > 0
    
    def integrate_frame_with_images(self,
                                    color: o3d.geometry.Image,
                                    depth: o3d.geometry.Image,
                                    pose: np.ndarray) -> bool:
        """
        画像オブジェクトから直接統合（深度推定用、GPU対応）
        
        Args:
            color: カラー画像
            depth: 深度画像
            pose: 4x4カメラポーズ行列
            
        Returns:
            成功したかどうか
        """
        if self.volume is None:
            self.create_volume()
        
        if self.intrinsic is None:
            raise ValueError("Camera intrinsics not set")
        
        try:
            color_np = np.asarray(color)
            depth_np = np.asarray(depth)
            img_h, img_w = color_np.shape[:2]
            
            # サイズ確認・リサイズ
            if color_np.shape[:2] != depth_np.shape[:2]:
                target_h, target_w = color_np.shape[:2]
                depth_resized = cv2.resize(depth_np, (target_w, target_h), 
                                           interpolation=cv2.INTER_NEAREST)
                depth = o3d.geometry.Image(depth_resized)
                depth_np = depth_resized
            
            # 画像サイズに基づいてintrinsicを調整
            frame_intrinsic = self._adjust_intrinsic(img_w, img_h)
            
            # Open3D座標系に変換
            o3d_pose = arcore_to_open3d_pose(pose)
            
            # Tensor APIのTSDFVolumeを使用している場合
            if self.is_tensor_volume and hasattr(self.volume, 'integrate'):
                # Tensor APIが利用可能か安全に確認
                try:
                    tensor_available = hasattr(o3d, 't') and hasattr(o3d.t, 'geometry')
                except (AttributeError, Exception):
                    tensor_available = False
                
                if tensor_available:
                    try:
                        # カラー画像をTensor形式に変換
                        color_array = np.asarray(color)
                        if len(color_array.shape) == 2:
                            color_array = np.stack([color_array, color_array, color_array], axis=-1)
                        color_tensor = o3d.core.Tensor(color_array, device=self.o3d_device)
                        color_img = o3d.t.geometry.Image(color_tensor)
                        
                        # 深度画像をTensor形式に変換（メートル単位）
                        depth_array = depth_np.astype(np.float32) / self.depth_scale
                        depth_tensor = o3d.core.Tensor(depth_array, device=self.o3d_device)
                        depth_img = o3d.t.geometry.Image(depth_tensor)
                        
                        # RGBD画像を作成（Tensor形式）
                        rgbd_tensor = o3d.t.geometry.RGBDImage(color_img, depth_img)
                        
                        # カメラ内部パラメータをTensor形式に変換
                        intrinsic_matrix = frame_intrinsic.intrinsic_matrix
                        intrinsic_tensor = o3d.core.Tensor(intrinsic_matrix, device=self.o3d_device)
                        
                        # ポーズをTensor形式に変換
                        pose_inv = np.linalg.inv(o3d_pose)
                        pose_tensor = o3d.core.Tensor(pose_inv, device=self.o3d_device)
                        
                        # Volumeに統合（Tensor API、GPU上で実行）
                        self.volume.integrate(rgbd_tensor, intrinsic_tensor, pose_tensor, self.depth_scale, self.depth_trunc)
                        return True
                    except Exception as e:
                        print(f"Tensor API integration failed: {e}, falling back to legacy API")
            
            # 通常のAPIを使用
            rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
                color, depth,
                depth_scale=self.depth_scale,
                depth_trunc=self.depth_trunc,
                convert_rgb_to_intensity=False
            )
            
            self.volume.integrate(rgbd, frame_intrinsic, np.linalg.inv(o3d_pose))
            return True
            
        except Exception as e:
            print(f"Frame integration error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_point_cloud(self) -> Optional[o3d.geometry.PointCloud]:
        """点群を抽出（GPU対応、Tensor APIを優先）"""
        if self.volume is None:
            return None
        
        try:
            # Tensor APIのTSDFVolumeの場合
            if hasattr(self.volume, 'extract_point_cloud') and hasattr(o3d, 't') and hasattr(o3d.t, 'geometry'):
                try:
                    # Tensor形式で点群を抽出（GPU上で処理）
                    pcd_tensor = self.volume.extract_point_cloud()
                    
                    # 点群の後処理をGPU上で実行
                    if self.use_gpu and hasattr(pcd_tensor, 'remove_statistical_outlier'):
                        pcd_tensor = self._process_point_cloud_tensor(pcd_tensor)
                    
                    # Tensor形式の場合は通常のPointCloudに変換
                    if hasattr(pcd_tensor, 'to_legacy'):
                        pcd = pcd_tensor.to_legacy()
                    else:
                        pcd = pcd_tensor
                    
                    # 後処理（CPU版も実行、互換性のため）
                    pcd = self._process_point_cloud_gpu(pcd)
                    return pcd
                except Exception as e:
                    print(f"Tensor API point cloud extraction failed: {e}, falling back to legacy API")
                    import traceback
                    traceback.print_exc()
            
            # 通常のAPIを使用（ScalableTSDFVolumeの場合）
            if hasattr(self.volume, 'extract_point_cloud'):
                pcd = self.volume.extract_point_cloud()
                
                # 点群の後処理（GPU対応）
                pcd = self._process_point_cloud_gpu(pcd)
                return pcd
            else:
                return None
        except Exception as e:
            print(f"Error extracting point cloud: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _process_point_cloud_tensor(self, pcd_tensor: o3d.t.geometry.PointCloud) -> o3d.t.geometry.PointCloud:
        """点群の後処理（Tensor形式、GPU上で実行）"""
        pcd_config = self.config.get('pointcloud', {})
        
        try:
            # 統計的外れ値除去（GPU上で実行）
            if pcd_config.get('remove_outliers', True):
                nb_neighbors = pcd_config.get('nb_neighbors', 20)
                std_ratio = pcd_config.get('std_ratio', 2.0)
                pcd_tensor, _ = pcd_tensor.remove_statistical_outlier(
                    nb_neighbors=nb_neighbors,
                    std_ratio=std_ratio
                )
            
            # 半径ベースの外れ値除去（GPU上で実行）
            if pcd_config.get('radius_outlier_removal', False):
                radius = pcd_config.get('radius', 0.05)
                min_neighbors = pcd_config.get('min_neighbors', 10)
                pcd_tensor, _ = pcd_tensor.remove_radius_outlier(
                    nb_points=min_neighbors,
                    search_radius=radius
                )
            
            return pcd_tensor
        except Exception as e:
            print(f"GPU tensor point cloud processing failed: {e}")
            return pcd_tensor
    
    def _process_point_cloud_gpu(self, pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
        """点群の後処理（GPU対応を試みる）"""
        pcd_config = self.config.get('pointcloud', {})
        
        # GPU対応の点群処理を試みる
        if self.use_gpu and hasattr(o3d, 't') and hasattr(o3d.t, 'geometry'):
            try:
                # Tensor形式の点群に変換
                pcd_tensor = o3d.t.geometry.PointCloud.from_legacy(pcd, device=self.o3d_device)
                
                # GPU上で処理
                pcd_tensor = self._process_point_cloud_tensor(pcd_tensor)
                
                # 通常のPointCloudに戻す
                pcd = pcd_tensor.to_legacy()
                return pcd
            except Exception as e:
                print(f"GPU point cloud processing failed: {e}, using CPU")
        
        # CPUで処理（フォールバック）
        if pcd_config.get('remove_outliers', True) and len(pcd.points) > 0:
            nb_neighbors = pcd_config.get('nb_neighbors', 20)
            std_ratio = pcd_config.get('std_ratio', 2.0)
            pcd, _ = pcd.remove_statistical_outlier(
                nb_neighbors=nb_neighbors,
                std_ratio=std_ratio
            )
        
        if pcd_config.get('radius_outlier_removal', False) and len(pcd.points) > 0:
            radius = pcd_config.get('radius', 0.05)
            min_neighbors = pcd_config.get('min_neighbors', 10)
            pcd, _ = pcd.remove_radius_outlier(
                nb_points=min_neighbors,
                radius=radius
            )
        
        return pcd
    
    def extract_mesh(self) -> Optional[o3d.geometry.TriangleMesh]:
        """メッシュを抽出（GPU対応、Tensor APIを優先）"""
        if self.volume is None:
            return None
        
        try:
            # Tensor APIのTSDFVolumeの場合
            if hasattr(self.volume, 'extract_triangle_mesh') and hasattr(o3d, 't') and hasattr(o3d.t, 'geometry'):
                try:
                    # Tensor形式でメッシュを抽出（GPU上で処理）
                    mesh_tensor = self.volume.extract_triangle_mesh()
                    
                    # Tensor形式の場合は通常のTriangleMeshに変換
                    if hasattr(mesh_tensor, 'to_legacy'):
                        mesh = mesh_tensor.to_legacy()
                    else:
                        mesh = mesh_tensor
                    
                    # GPU上で法線計算を試みる
                    if self.use_gpu and hasattr(mesh, 'compute_vertex_normals'):
                        mesh.compute_vertex_normals()
                    else:
                        mesh.compute_vertex_normals()
                    
                    return mesh
                except Exception as e:
                    print(f"Tensor API mesh extraction failed: {e}, falling back to legacy API")
            
            # 通常のAPIを使用（ScalableTSDFVolumeの場合）
            if hasattr(self.volume, 'extract_triangle_mesh'):
                mesh = self.volume.extract_triangle_mesh()
                mesh.compute_vertex_normals()
                return mesh
            else:
                return None
        except Exception as e:
            print(f"Error extracting mesh: {e}")
            import traceback
            traceback.print_exc()
            return None



