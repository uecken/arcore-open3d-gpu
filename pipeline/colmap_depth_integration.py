#!/usr/bin/env python3
"""
方法C: スケール補正付きCOLMAP深度統合

COLMAPの滑らかな深度マップとARCoreの正確な位置姿勢を組み合わせて、
高品質なメッシュを生成します。

主な特徴:
- 深度: COLMAPのPatch Match Stereoで生成（滑らかで一貫性あり）
- 位置姿勢: ARCoreのVIO（高精度、実寸メートル単位）
- 統合: GPU TSDF Volume（高速、大規模データ対応）
"""

import struct
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
import json
import re

try:
    import open3d as o3d
    import open3d.core as o3c
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False

try:
    from utils.arcore_parser import ARCoreDataParser
except ImportError:
    from .arcore_data_parser import ARCoreDataParser


class COLMAPDepthIntegration:
    """スケール補正付きCOLMAP深度統合パイプライン"""
    
    def __init__(self, config: dict):
        self.config = config
        self.colmap_depth_config = config.get('colmap_depth', {})
        self.gpu_enabled = config.get('gpu', {}).get('enabled', True)
        
        # TSDF設定
        self.voxel_size = self.colmap_depth_config.get('voxel_size', 0.01)
        self.block_resolution = self.colmap_depth_config.get('block_resolution', 16)
        self.block_count = self.colmap_depth_config.get('block_count', 100000)
        
        # 深度設定
        self.depth_scale = self.colmap_depth_config.get('depth_scale', 1.0)
        self.depth_max = self.colmap_depth_config.get('depth_max', 5.0)
        self.depth_min = self.colmap_depth_config.get('depth_min', 0.1)
        
        # メッシュ設定
        self.mesh_weight_threshold = self.colmap_depth_config.get('mesh_weight_threshold', 3.0)
        self.skip_unregistered = self.colmap_depth_config.get('skip_unregistered', True)
        
        # デバイス設定
        if self.gpu_enabled and HAS_OPEN3D:
            try:
                self.device = o3c.Device("CUDA:0")
                print(f"✓ COLMAP Depth Integration: Using GPU (CUDA:0)")
            except Exception as e:
                print(f"⚠ GPU not available, using CPU: {e}")
                self.device = o3c.Device("CPU:0")
        else:
            self.device = o3c.Device("CPU:0") if HAS_OPEN3D else None
            print(f"✓ COLMAP Depth Integration: Using CPU")
    
    def read_colmap_depth_map(self, path: Path) -> Optional[np.ndarray]:
        """
        COLMAP深度マップを読み込む
        
        COLMAP形式: テキストヘッダー "HEIGHT&WIDTH&CHANNELS&" + float32バイナリデータ
        
        Args:
            path: .geometric.bin または .photometric.bin ファイルパス
        
        Returns:
            深度マップ (H, W) float32、失敗時はNone
        """
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            # テキストヘッダーを解析 (例: "480&640&1&")
            # ヘッダー終端を探す (3つの&の後)
            header_end = 0
            ampersand_count = 0
            for i, byte in enumerate(data):
                if byte == ord('&'):
                    ampersand_count += 1
                    if ampersand_count == 3:
                        header_end = i + 1
                        break
            
            if header_end == 0:
                print(f"⚠ Invalid COLMAP depth map format: {path}")
                return None
            
            # ヘッダーをパース
            header_str = data[:header_end].decode('ascii')
            parts = header_str.split('&')
            if len(parts) < 3:
                print(f"⚠ Invalid header format: {header_str}")
                return None
            
            height = int(parts[0])
            width = int(parts[1])
            channels = int(parts[2])
            
            if channels != 1:
                print(f"⚠ Unexpected channels: {channels} (expected 1)")
            
            # 深度データ読み込み
            depth_data = np.frombuffer(data[header_end:], dtype=np.float32)
            expected_size = height * width * channels
            
            if len(depth_data) < expected_size:
                print(f"⚠ Insufficient depth data: {len(depth_data)} < {expected_size}")
                return None
            
            depth = depth_data[:expected_size].reshape(height, width)
            
            return depth
                
        except Exception as e:
            print(f"Error reading COLMAP depth map {path}: {e}")
            return None
    
    def get_registered_images(self, colmap_dir: Path) -> Dict[str, dict]:
        """
        COLMAPで登録された画像情報を取得
        
        Returns:
            {image_name: {'image_id': int, 'camera_id': int, 'qvec': array, 'tvec': array}}
        """
        images = {}
        
        # sparse/*/images.bin を読み込む
        sparse_dirs = sorted(colmap_dir.glob("sparse/*"))
        if not sparse_dirs:
            print("⚠ No sparse models found")
            return images
        
        # 最大のモデルを選択
        largest_model = None
        largest_size = 0
        for sparse_dir in sparse_dirs:
            images_bin = sparse_dir / "images.bin"
            images_txt = sparse_dir / "images.txt"
            if images_bin.exists():
                size = images_bin.stat().st_size
                if size > largest_size:
                    largest_size = size
                    largest_model = images_bin
            elif images_txt.exists():
                size = images_txt.stat().st_size
                if size > largest_size:
                    largest_size = size
                    largest_model = images_txt
        
        if largest_model is None:
            print("⚠ No images.bin or images.txt found")
            return images
        
        print(f"  Using sparse model: {largest_model.parent.name}")
        
        if largest_model.suffix == '.bin':
            images = self._read_images_bin(largest_model)
        else:
            images = self._read_images_txt(largest_model)
        
        return images
    
    def _read_images_bin(self, path: Path) -> Dict[str, dict]:
        """images.binを読み込み"""
        images = {}
        try:
            with open(path, 'rb') as f:
                num_images = struct.unpack('Q', f.read(8))[0]
                
                for _ in range(num_images):
                    image_id = struct.unpack('I', f.read(4))[0]
                    qvec = np.array(struct.unpack('dddd', f.read(32)))
                    tvec = np.array(struct.unpack('ddd', f.read(24)))
                    camera_id = struct.unpack('I', f.read(4))[0]
                    
                    # 画像名を読み込む
                    name = b''
                    while True:
                        c = f.read(1)
                        if c == b'\x00':
                            break
                        name += c
                    image_name = name.decode('utf-8')
                    
                    # 2D点の数を読み込んでスキップ
                    num_points2d = struct.unpack('Q', f.read(8))[0]
                    f.read(num_points2d * 24)  # x, y, point3D_id (8+8+8 bytes)
                    
                    images[image_name] = {
                        'image_id': image_id,
                        'camera_id': camera_id,
                        'qvec': qvec,
                        'tvec': tvec
                    }
                    
        except Exception as e:
            print(f"Error reading images.bin: {e}")
        
        return images
    
    def _read_images_txt(self, path: Path) -> Dict[str, dict]:
        """images.txtを読み込み"""
        images = {}
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 10:
                        image_id = int(parts[0])
                        qvec = np.array([float(x) for x in parts[1:5]])
                        tvec = np.array([float(x) for x in parts[5:8]])
                        camera_id = int(parts[8])
                        image_name = parts[9]
                        
                        images[image_name] = {
                            'image_id': image_id,
                            'camera_id': camera_id,
                            'qvec': qvec,
                            'tvec': tvec
                        }
                        
                        # 次の行（2D点）をスキップ
                        next(f, None)
                        
        except Exception as e:
            print(f"Error reading images.txt: {e}")
        
        return images
    
    def compute_scale_factor(
        self,
        arcore_poses: Dict[str, np.ndarray],
        colmap_images: Dict[str, dict]
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Procrustes分析でスケール係数を計算
        
        Returns:
            (scale, rotation_matrix, translation)
        """
        # 共通画像を見つける
        common_images = []
        for img_name in colmap_images.keys():
            # frame_xxxxx.jpg -> xxxxx のマッピング
            base_name = Path(img_name).stem
            timestamp = base_name.replace('frame_', '')
            
            if timestamp in arcore_poses:
                common_images.append((img_name, timestamp))
        
        if len(common_images) < 10:
            print(f"⚠ Only {len(common_images)} common images found")
            return 1.0, np.eye(3), np.zeros(3)
        
        print(f"  Common images for scale calculation: {len(common_images)}")
        
        # カメラ位置を収集
        arcore_pts = []
        colmap_pts = []
        
        for img_name, timestamp in common_images:
            arcore_pts.append(arcore_poses[timestamp][:3, 3])
            
            # COLMAP: qvec, tvec -> 位置
            colmap_img = colmap_images[img_name]
            R = self._qvec_to_rotation(colmap_img['qvec'])
            t = colmap_img['tvec']
            # カメラ位置 = -R^T * t
            colmap_pts.append(-R.T @ t)
        
        arcore_pts = np.array(arcore_pts)
        colmap_pts = np.array(colmap_pts)
        
        # Procrustes分析
        arcore_centroid = arcore_pts.mean(axis=0)
        colmap_centroid = colmap_pts.mean(axis=0)
        
        arcore_centered = arcore_pts - arcore_centroid
        colmap_centered = colmap_pts - colmap_centroid
        
        arcore_scale_norm = np.sqrt((arcore_centered ** 2).sum())
        colmap_scale_norm = np.sqrt((colmap_centered ** 2).sum())
        
        if colmap_scale_norm < 1e-6:
            print("⚠ COLMAP scale too small")
            return 1.0, np.eye(3), np.zeros(3)
        
        scale = arcore_scale_norm / colmap_scale_norm
        
        # 回転行列
        from scipy.linalg import orthogonal_procrustes
        arcore_normalized = arcore_centered / arcore_scale_norm
        colmap_normalized = colmap_centered / colmap_scale_norm
        R, _ = orthogonal_procrustes(colmap_normalized, arcore_normalized)
        
        # 平行移動
        translation = arcore_centroid - scale * (colmap_centroid @ R)
        
        print(f"  Scale factor: {scale:.4f}")
        print(f"  Translation: [{translation[0]:.3f}, {translation[1]:.3f}, {translation[2]:.3f}]")
        
        return scale, R, translation
    
    def _qvec_to_rotation(self, qvec: np.ndarray) -> np.ndarray:
        """クォータニオンを回転行列に変換"""
        w, x, y, z = qvec
        return np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
            [2*x*y + 2*w*z, 1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
            [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x*x - 2*y*y]
        ])
    
    def process_session(
        self,
        session_dir: Path,
        output_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> Tuple[Optional[Path], Optional[Path], dict]:
        """
        方法Cでセッションを処理
        
        Args:
            session_dir: セッションデータディレクトリ
            output_dir: 出力ディレクトリ
            progress_callback: 進捗コールバック(percent, message)
        
        Returns:
            (point_cloud_path, mesh_path, stats)
        """
        stats = {
            'mode': 'colmap_depth',
            'frames_processed': 0,
            'frames_skipped': 0,
            'scale_factor': 1.0,
            'voxel_size': self.voxel_size
        }
        
        if not HAS_OPEN3D:
            print("Error: Open3D not available")
            return None, None, stats
        
        if progress_callback:
            progress_callback(5, "Loading ARCore data...")
        
        # ARCoreデータを読み込み
        parser = ARCoreDataParser(session_dir)
        if not parser.parse():
            print("Error: Failed to parse ARCore data")
            return None, None, stats
        
        # ポーズを辞書形式に変換 (timestamp -> 4x4 matrix)
        arcore_poses = {}
        for timestamp, pose in parser.poses.items():
            matrix = pose.to_matrix()
            arcore_poses[str(timestamp)] = matrix
        
        # カメラ内部パラメータ
        intrinsics = {
            'fx': parser.intrinsics.fx if parser.intrinsics else 500,
            'fy': parser.intrinsics.fy if parser.intrinsics else 500,
            'cx': parser.intrinsics.cx if parser.intrinsics else 320,
            'cy': parser.intrinsics.cy if parser.intrinsics else 240,
        }
        
        if not arcore_poses:
            print("Error: No ARCore poses found")
            return None, None, stats
        
        print(f"  ARCore poses loaded: {len(arcore_poses)}")
        
        # COLMAPディレクトリを確認
        colmap_dir = session_dir / "colmap"
        if not colmap_dir.exists():
            print("Error: COLMAP directory not found")
            print("  Please run COLMAP MVS pipeline first")
            return None, None, stats
        
        if progress_callback:
            progress_callback(10, "Loading COLMAP data...")
        
        # COLMAP登録画像を取得
        colmap_images = self.get_registered_images(colmap_dir)
        if not colmap_images:
            print("Error: No COLMAP registered images found")
            return None, None, stats
        
        print(f"  COLMAP registered images: {len(colmap_images)}")
        
        # 深度マップディレクトリ
        depth_maps_dir = colmap_dir / "dense" / "stereo" / "depth_maps"
        if not depth_maps_dir.exists():
            print("Error: COLMAP depth maps not found")
            print("  Please run COLMAP Patch Match Stereo first")
            return None, None, stats
        
        if progress_callback:
            progress_callback(15, "Computing scale factor...")
        
        # スケール係数を計算
        scale, rotation, translation = self.compute_scale_factor(
            arcore_poses, colmap_images
        )
        stats['scale_factor'] = float(scale)
        
        if progress_callback:
            progress_callback(20, "Initializing GPU TSDF Volume...")
        
        # GPU TSDF Volume作成
        try:
            vbg = o3d.t.geometry.VoxelBlockGrid(
                attr_names=('tsdf', 'weight', 'color'),
                attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
                attr_channels=(1, 1, 3),
                voxel_size=self.voxel_size,
                block_resolution=self.block_resolution,
                block_count=self.block_count,
                device=self.device
            )
            print(f"  TSDF Volume created (voxel_size={self.voxel_size}m, device={self.device})")
        except Exception as e:
            print(f"Error creating TSDF Volume: {e}")
            return None, None, stats
        
        # カメラ内部パラメータ（CPUに置く必要がある）
        fx = intrinsics.get('fx', 500)
        fy = intrinsics.get('fy', 500)
        cx = intrinsics.get('cx', 320)
        cy = intrinsics.get('cy', 240)
        
        cpu_device = o3c.Device("CPU:0")
        intrinsic_tensor = o3c.Tensor(
            [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
            dtype=o3c.float64,
            device=cpu_device
        )
        
        if progress_callback:
            progress_callback(25, "Integrating depth maps...")
        
        # 各フレームを統合
        total_images = len(colmap_images)
        processed = 0
        skipped = 0
        
        for i, (img_name, img_data) in enumerate(colmap_images.items()):
            # 深度マップを読み込む
            depth_map_path = depth_maps_dir / f"{img_name}.geometric.bin"
            if not depth_map_path.exists():
                depth_map_path = depth_maps_dir / f"{img_name}.photometric.bin"
            
            if not depth_map_path.exists():
                skipped += 1
                continue
            
            depth = self.read_colmap_depth_map(depth_map_path)
            if depth is None:
                skipped += 1
                continue
            
            # スケール補正
            depth_scaled = depth * scale
            
            # 無効な深度をマスク
            depth_scaled[depth_scaled < self.depth_min] = 0
            depth_scaled[depth_scaled > self.depth_max] = 0
            
            # タイムスタンプからARCoreポーズを取得
            base_name = Path(img_name).stem
            timestamp = base_name.replace('frame_', '')
            
            if timestamp not in arcore_poses:
                skipped += 1
                continue
            
            arcore_pose = arcore_poses[timestamp]
            
            # GPU Tensor/Imageに変換
            depth_tensor = o3c.Tensor(
                depth_scaled.astype(np.float32),
                dtype=o3c.float32,
                device=self.device
            )
            
            # ImageオブジェクトとしてラップOpen3D T.geometry用）
            depth_image = o3d.t.geometry.Image(depth_tensor)
            
            # 外部パラメータ（ARCoreポーズ）- CPUに置く必要がある
            extrinsic = o3c.Tensor(
                np.linalg.inv(arcore_pose).astype(np.float64),
                dtype=o3c.float64,
                device=cpu_device
            )
            
            try:
                # ブロック座標を計算（Imageオブジェクトを使用）
                frustum_block_coords = vbg.compute_unique_block_coordinates(
                    depth_image, intrinsic_tensor, extrinsic,
                    depth_scale=1.0, depth_max=self.depth_max
                )
                
                # TSDF統合（Imageオブジェクトを使用）
                vbg.integrate(
                    block_coords=frustum_block_coords,
                    depth=depth_image,
                    intrinsic=intrinsic_tensor,
                    extrinsic=extrinsic,
                    depth_scale=1.0,
                    depth_max=self.depth_max
                )
                
                processed += 1
                
            except Exception as e:
                print(f"  ⚠ Error integrating {img_name}: {e}")
                skipped += 1
                continue
            
            # 進捗更新
            if progress_callback and (i + 1) % 50 == 0:
                progress = 25 + int(50 * (i + 1) / total_images)
                progress_callback(
                    progress,
                    f"Integrating: {i+1}/{total_images} ({processed} processed, {skipped} skipped)"
                )
        
        stats['frames_processed'] = processed
        stats['frames_skipped'] = skipped
        
        print(f"  Processed: {processed}, Skipped: {skipped}")
        
        if processed < 10:
            print("Error: Too few frames processed")
            return None, None, stats
        
        if progress_callback:
            progress_callback(80, "Extracting point cloud...")
        
        # 点群抽出
        try:
            pcd = vbg.extract_point_cloud(weight_threshold=self.mesh_weight_threshold)
            pcd_legacy = pcd.to_legacy()
            
            # 点群を保存（標準ファイル名でViewer互換）
            output_dir.mkdir(parents=True, exist_ok=True)
            pcd_path = output_dir / "point_cloud.ply"
            o3d.io.write_point_cloud(str(pcd_path), pcd_legacy)
            
            stats['point_count'] = len(pcd_legacy.points)
            print(f"  Point cloud saved: {stats['point_count']} points")
            
        except Exception as e:
            print(f"Error extracting point cloud: {e}")
            pcd_path = None
        
        if progress_callback:
            progress_callback(90, "Extracting mesh...")
        
        # メッシュ抽出
        mesh_path = None
        try:
            mesh = vbg.extract_triangle_mesh(weight_threshold=self.mesh_weight_threshold)
            mesh_legacy = mesh.to_legacy()
            
            # 法線計算
            mesh_legacy.compute_vertex_normals()
            
            # メッシュを保存（標準ファイル名でViewer互換）
            mesh_path = output_dir / "mesh.ply"
            o3d.io.write_triangle_mesh(str(mesh_path), mesh_legacy)
            
            stats['vertex_count'] = len(mesh_legacy.vertices)
            stats['triangle_count'] = len(mesh_legacy.triangles)
            print(f"  Mesh saved: {stats['vertex_count']} vertices, {stats['triangle_count']} triangles")
            
        except Exception as e:
            print(f"  GPU mesh extraction failed: {e}")
            print(f"  Trying CPU mesh extraction...")
            
            try:
                # CPUに転送してメッシュ抽出
                vbg_cpu = vbg.cpu()
                mesh = vbg_cpu.extract_triangle_mesh(weight_threshold=self.mesh_weight_threshold)
                mesh_legacy = mesh.to_legacy()
                
                mesh_legacy.compute_vertex_normals()
                
                mesh_path = output_dir / "mesh.ply"
                o3d.io.write_triangle_mesh(str(mesh_path), mesh_legacy)
                
                stats['vertex_count'] = len(mesh_legacy.vertices)
                stats['triangle_count'] = len(mesh_legacy.triangles)
                print(f"  Mesh saved (CPU): {stats['vertex_count']} vertices, {stats['triangle_count']} triangles")
                
            except Exception as e2:
                print(f"  CPU mesh extraction also failed: {e2}")
                print(f"  Creating mesh from point cloud using Poisson reconstruction...")
                
                try:
                    # 点群からPoissonでメッシュ生成
                    if pcd_legacy and len(pcd_legacy.points) > 100:
                        pcd_legacy.estimate_normals()
                        mesh_legacy, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                            pcd_legacy, depth=9
                        )
                        
                        mesh_path = output_dir / "mesh.ply"
                        o3d.io.write_triangle_mesh(str(mesh_path), mesh_legacy)
                        
                        stats['vertex_count'] = len(mesh_legacy.vertices)
                        stats['triangle_count'] = len(mesh_legacy.triangles)
                        print(f"  Mesh saved (Poisson): {stats['vertex_count']} vertices, {stats['triangle_count']} triangles")
                        
                except Exception as e3:
                    print(f"  Poisson reconstruction failed: {e3}")
        
        # 変換パラメータを保存
        transform_data = {
            'scale': float(scale),
            'rotation': rotation.tolist(),
            'translation': translation.tolist(),
            'method': 'colmap_depth_integration'
        }
        transform_path = output_dir / "colmap_depth_transform.json"
        with open(transform_path, 'w') as f:
            json.dump(transform_data, f, indent=2)
        
        # ARCore軌跡を保存（Viewer表示用）
        trajectory_data = {
            'coordinate_system': 'arcore',
            'unit': 'meters',
            'count': len(arcore_poses),
            'poses': []
        }
        for timestamp in sorted(arcore_poses.keys()):
            pose = arcore_poses[timestamp]
            trajectory_data['poses'].append({
                'timestamp': timestamp,
                'position': pose[:3, 3].tolist(),
                'rotation': pose[:3, :3].tolist()
            })
        trajectory_path = output_dir / "trajectory.json"
        with open(trajectory_path, 'w') as f:
            json.dump(trajectory_data, f, indent=2)
        print(f"  Trajectory saved: {len(arcore_poses)} poses")
        
        if progress_callback:
            progress_callback(100, "Processing complete")
        
        return pcd_path, mesh_path, stats


def run_colmap_depth_pipeline(
    session_dir: Path,
    output_dir: Path,
    config: dict,
    progress_callback: Callable[[int, str], None] = None
) -> Tuple[Optional[Path], Optional[Path], dict]:
    """
    方法C: スケール補正付きCOLMAP深度統合パイプラインを実行
    
    前提条件:
    - COLMAPのMVS処理が完了していること
    - dense/stereo/depth_maps/*.geometric.bin が存在すること
    
    Args:
        session_dir: セッションデータディレクトリ
        output_dir: 出力ディレクトリ
        config: 設定辞書
        progress_callback: 進捗コールバック
    
    Returns:
        (point_cloud_path, mesh_path, stats)
    """
    pipeline = COLMAPDepthIntegration(config)
    return pipeline.process_session(session_dir, output_dir, progress_callback)


方法C: スケール補正付きCOLMAP深度統合

COLMAPの滑らかな深度マップとARCoreの正確な位置姿勢を組み合わせて、
高品質なメッシュを生成します。

主な特徴:
- 深度: COLMAPのPatch Match Stereoで生成（滑らかで一貫性あり）
- 位置姿勢: ARCoreのVIO（高精度、実寸メートル単位）
- 統合: GPU TSDF Volume（高速、大規模データ対応）
"""

import struct
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
import json
import re

try:
    import open3d as o3d
    import open3d.core as o3c
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False

try:
    from utils.arcore_parser import ARCoreDataParser
except ImportError:
    from .arcore_data_parser import ARCoreDataParser


class COLMAPDepthIntegration:
    """スケール補正付きCOLMAP深度統合パイプライン"""
    
    def __init__(self, config: dict):
        self.config = config
        self.colmap_depth_config = config.get('colmap_depth', {})
        self.gpu_enabled = config.get('gpu', {}).get('enabled', True)
        
        # TSDF設定
        self.voxel_size = self.colmap_depth_config.get('voxel_size', 0.01)
        self.block_resolution = self.colmap_depth_config.get('block_resolution', 16)
        self.block_count = self.colmap_depth_config.get('block_count', 100000)
        
        # 深度設定
        self.depth_scale = self.colmap_depth_config.get('depth_scale', 1.0)
        self.depth_max = self.colmap_depth_config.get('depth_max', 5.0)
        self.depth_min = self.colmap_depth_config.get('depth_min', 0.1)
        
        # メッシュ設定
        self.mesh_weight_threshold = self.colmap_depth_config.get('mesh_weight_threshold', 3.0)
        self.skip_unregistered = self.colmap_depth_config.get('skip_unregistered', True)
        
        # デバイス設定
        if self.gpu_enabled and HAS_OPEN3D:
            try:
                self.device = o3c.Device("CUDA:0")
                print(f"✓ COLMAP Depth Integration: Using GPU (CUDA:0)")
            except Exception as e:
                print(f"⚠ GPU not available, using CPU: {e}")
                self.device = o3c.Device("CPU:0")
        else:
            self.device = o3c.Device("CPU:0") if HAS_OPEN3D else None
            print(f"✓ COLMAP Depth Integration: Using CPU")
    
    def read_colmap_depth_map(self, path: Path) -> Optional[np.ndarray]:
        """
        COLMAP深度マップを読み込む
        
        COLMAP形式: テキストヘッダー "HEIGHT&WIDTH&CHANNELS&" + float32バイナリデータ
        
        Args:
            path: .geometric.bin または .photometric.bin ファイルパス
        
        Returns:
            深度マップ (H, W) float32、失敗時はNone
        """
        try:
            with open(path, 'rb') as f:
                data = f.read()
            
            # テキストヘッダーを解析 (例: "480&640&1&")
            # ヘッダー終端を探す (3つの&の後)
            header_end = 0
            ampersand_count = 0
            for i, byte in enumerate(data):
                if byte == ord('&'):
                    ampersand_count += 1
                    if ampersand_count == 3:
                        header_end = i + 1
                        break
            
            if header_end == 0:
                print(f"⚠ Invalid COLMAP depth map format: {path}")
                return None
            
            # ヘッダーをパース
            header_str = data[:header_end].decode('ascii')
            parts = header_str.split('&')
            if len(parts) < 3:
                print(f"⚠ Invalid header format: {header_str}")
                return None
            
            height = int(parts[0])
            width = int(parts[1])
            channels = int(parts[2])
            
            if channels != 1:
                print(f"⚠ Unexpected channels: {channels} (expected 1)")
            
            # 深度データ読み込み
            depth_data = np.frombuffer(data[header_end:], dtype=np.float32)
            expected_size = height * width * channels
            
            if len(depth_data) < expected_size:
                print(f"⚠ Insufficient depth data: {len(depth_data)} < {expected_size}")
                return None
            
            depth = depth_data[:expected_size].reshape(height, width)
            
            return depth
                
        except Exception as e:
            print(f"Error reading COLMAP depth map {path}: {e}")
            return None
    
    def get_registered_images(self, colmap_dir: Path) -> Dict[str, dict]:
        """
        COLMAPで登録された画像情報を取得
        
        Returns:
            {image_name: {'image_id': int, 'camera_id': int, 'qvec': array, 'tvec': array}}
        """
        images = {}
        
        # sparse/*/images.bin を読み込む
        sparse_dirs = sorted(colmap_dir.glob("sparse/*"))
        if not sparse_dirs:
            print("⚠ No sparse models found")
            return images
        
        # 最大のモデルを選択
        largest_model = None
        largest_size = 0
        for sparse_dir in sparse_dirs:
            images_bin = sparse_dir / "images.bin"
            images_txt = sparse_dir / "images.txt"
            if images_bin.exists():
                size = images_bin.stat().st_size
                if size > largest_size:
                    largest_size = size
                    largest_model = images_bin
            elif images_txt.exists():
                size = images_txt.stat().st_size
                if size > largest_size:
                    largest_size = size
                    largest_model = images_txt
        
        if largest_model is None:
            print("⚠ No images.bin or images.txt found")
            return images
        
        print(f"  Using sparse model: {largest_model.parent.name}")
        
        if largest_model.suffix == '.bin':
            images = self._read_images_bin(largest_model)
        else:
            images = self._read_images_txt(largest_model)
        
        return images
    
    def _read_images_bin(self, path: Path) -> Dict[str, dict]:
        """images.binを読み込み"""
        images = {}
        try:
            with open(path, 'rb') as f:
                num_images = struct.unpack('Q', f.read(8))[0]
                
                for _ in range(num_images):
                    image_id = struct.unpack('I', f.read(4))[0]
                    qvec = np.array(struct.unpack('dddd', f.read(32)))
                    tvec = np.array(struct.unpack('ddd', f.read(24)))
                    camera_id = struct.unpack('I', f.read(4))[0]
                    
                    # 画像名を読み込む
                    name = b''
                    while True:
                        c = f.read(1)
                        if c == b'\x00':
                            break
                        name += c
                    image_name = name.decode('utf-8')
                    
                    # 2D点の数を読み込んでスキップ
                    num_points2d = struct.unpack('Q', f.read(8))[0]
                    f.read(num_points2d * 24)  # x, y, point3D_id (8+8+8 bytes)
                    
                    images[image_name] = {
                        'image_id': image_id,
                        'camera_id': camera_id,
                        'qvec': qvec,
                        'tvec': tvec
                    }
                    
        except Exception as e:
            print(f"Error reading images.bin: {e}")
        
        return images
    
    def _read_images_txt(self, path: Path) -> Dict[str, dict]:
        """images.txtを読み込み"""
        images = {}
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 10:
                        image_id = int(parts[0])
                        qvec = np.array([float(x) for x in parts[1:5]])
                        tvec = np.array([float(x) for x in parts[5:8]])
                        camera_id = int(parts[8])
                        image_name = parts[9]
                        
                        images[image_name] = {
                            'image_id': image_id,
                            'camera_id': camera_id,
                            'qvec': qvec,
                            'tvec': tvec
                        }
                        
                        # 次の行（2D点）をスキップ
                        next(f, None)
                        
        except Exception as e:
            print(f"Error reading images.txt: {e}")
        
        return images
    
    def compute_scale_factor(
        self,
        arcore_poses: Dict[str, np.ndarray],
        colmap_images: Dict[str, dict]
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Procrustes分析でスケール係数を計算
        
        Returns:
            (scale, rotation_matrix, translation)
        """
        # 共通画像を見つける
        common_images = []
        for img_name in colmap_images.keys():
            # frame_xxxxx.jpg -> xxxxx のマッピング
            base_name = Path(img_name).stem
            timestamp = base_name.replace('frame_', '')
            
            if timestamp in arcore_poses:
                common_images.append((img_name, timestamp))
        
        if len(common_images) < 10:
            print(f"⚠ Only {len(common_images)} common images found")
            return 1.0, np.eye(3), np.zeros(3)
        
        print(f"  Common images for scale calculation: {len(common_images)}")
        
        # カメラ位置を収集
        arcore_pts = []
        colmap_pts = []
        
        for img_name, timestamp in common_images:
            arcore_pts.append(arcore_poses[timestamp][:3, 3])
            
            # COLMAP: qvec, tvec -> 位置
            colmap_img = colmap_images[img_name]
            R = self._qvec_to_rotation(colmap_img['qvec'])
            t = colmap_img['tvec']
            # カメラ位置 = -R^T * t
            colmap_pts.append(-R.T @ t)
        
        arcore_pts = np.array(arcore_pts)
        colmap_pts = np.array(colmap_pts)
        
        # Procrustes分析
        arcore_centroid = arcore_pts.mean(axis=0)
        colmap_centroid = colmap_pts.mean(axis=0)
        
        arcore_centered = arcore_pts - arcore_centroid
        colmap_centered = colmap_pts - colmap_centroid
        
        arcore_scale_norm = np.sqrt((arcore_centered ** 2).sum())
        colmap_scale_norm = np.sqrt((colmap_centered ** 2).sum())
        
        if colmap_scale_norm < 1e-6:
            print("⚠ COLMAP scale too small")
            return 1.0, np.eye(3), np.zeros(3)
        
        scale = arcore_scale_norm / colmap_scale_norm
        
        # 回転行列
        from scipy.linalg import orthogonal_procrustes
        arcore_normalized = arcore_centered / arcore_scale_norm
        colmap_normalized = colmap_centered / colmap_scale_norm
        R, _ = orthogonal_procrustes(colmap_normalized, arcore_normalized)
        
        # 平行移動
        translation = arcore_centroid - scale * (colmap_centroid @ R)
        
        print(f"  Scale factor: {scale:.4f}")
        print(f"  Translation: [{translation[0]:.3f}, {translation[1]:.3f}, {translation[2]:.3f}]")
        
        return scale, R, translation
    
    def _qvec_to_rotation(self, qvec: np.ndarray) -> np.ndarray:
        """クォータニオンを回転行列に変換"""
        w, x, y, z = qvec
        return np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
            [2*x*y + 2*w*z, 1 - 2*x*x - 2*z*z, 2*y*z - 2*w*x],
            [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x*x - 2*y*y]
        ])
    
    def process_session(
        self,
        session_dir: Path,
        output_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> Tuple[Optional[Path], Optional[Path], dict]:
        """
        方法Cでセッションを処理
        
        Args:
            session_dir: セッションデータディレクトリ
            output_dir: 出力ディレクトリ
            progress_callback: 進捗コールバック(percent, message)
        
        Returns:
            (point_cloud_path, mesh_path, stats)
        """
        stats = {
            'mode': 'colmap_depth',
            'frames_processed': 0,
            'frames_skipped': 0,
            'scale_factor': 1.0,
            'voxel_size': self.voxel_size
        }
        
        if not HAS_OPEN3D:
            print("Error: Open3D not available")
            return None, None, stats
        
        if progress_callback:
            progress_callback(5, "Loading ARCore data...")
        
        # ARCoreデータを読み込み
        parser = ARCoreDataParser(session_dir)
        if not parser.parse():
            print("Error: Failed to parse ARCore data")
            return None, None, stats
        
        # ポーズを辞書形式に変換 (timestamp -> 4x4 matrix)
        arcore_poses = {}
        for timestamp, pose in parser.poses.items():
            matrix = pose.to_matrix()
            arcore_poses[str(timestamp)] = matrix
        
        # カメラ内部パラメータ
        intrinsics = {
            'fx': parser.intrinsics.fx if parser.intrinsics else 500,
            'fy': parser.intrinsics.fy if parser.intrinsics else 500,
            'cx': parser.intrinsics.cx if parser.intrinsics else 320,
            'cy': parser.intrinsics.cy if parser.intrinsics else 240,
        }
        
        if not arcore_poses:
            print("Error: No ARCore poses found")
            return None, None, stats
        
        print(f"  ARCore poses loaded: {len(arcore_poses)}")
        
        # COLMAPディレクトリを確認
        colmap_dir = session_dir / "colmap"
        if not colmap_dir.exists():
            print("Error: COLMAP directory not found")
            print("  Please run COLMAP MVS pipeline first")
            return None, None, stats
        
        if progress_callback:
            progress_callback(10, "Loading COLMAP data...")
        
        # COLMAP登録画像を取得
        colmap_images = self.get_registered_images(colmap_dir)
        if not colmap_images:
            print("Error: No COLMAP registered images found")
            return None, None, stats
        
        print(f"  COLMAP registered images: {len(colmap_images)}")
        
        # 深度マップディレクトリ
        depth_maps_dir = colmap_dir / "dense" / "stereo" / "depth_maps"
        if not depth_maps_dir.exists():
            print("Error: COLMAP depth maps not found")
            print("  Please run COLMAP Patch Match Stereo first")
            return None, None, stats
        
        if progress_callback:
            progress_callback(15, "Computing scale factor...")
        
        # スケール係数を計算
        scale, rotation, translation = self.compute_scale_factor(
            arcore_poses, colmap_images
        )
        stats['scale_factor'] = float(scale)
        
        if progress_callback:
            progress_callback(20, "Initializing GPU TSDF Volume...")
        
        # GPU TSDF Volume作成
        try:
            vbg = o3d.t.geometry.VoxelBlockGrid(
                attr_names=('tsdf', 'weight', 'color'),
                attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
                attr_channels=(1, 1, 3),
                voxel_size=self.voxel_size,
                block_resolution=self.block_resolution,
                block_count=self.block_count,
                device=self.device
            )
            print(f"  TSDF Volume created (voxel_size={self.voxel_size}m, device={self.device})")
        except Exception as e:
            print(f"Error creating TSDF Volume: {e}")
            return None, None, stats
        
        # カメラ内部パラメータ（CPUに置く必要がある）
        fx = intrinsics.get('fx', 500)
        fy = intrinsics.get('fy', 500)
        cx = intrinsics.get('cx', 320)
        cy = intrinsics.get('cy', 240)
        
        cpu_device = o3c.Device("CPU:0")
        intrinsic_tensor = o3c.Tensor(
            [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
            dtype=o3c.float64,
            device=cpu_device
        )
        
        if progress_callback:
            progress_callback(25, "Integrating depth maps...")
        
        # 各フレームを統合
        total_images = len(colmap_images)
        processed = 0
        skipped = 0
        
        for i, (img_name, img_data) in enumerate(colmap_images.items()):
            # 深度マップを読み込む
            depth_map_path = depth_maps_dir / f"{img_name}.geometric.bin"
            if not depth_map_path.exists():
                depth_map_path = depth_maps_dir / f"{img_name}.photometric.bin"
            
            if not depth_map_path.exists():
                skipped += 1
                continue
            
            depth = self.read_colmap_depth_map(depth_map_path)
            if depth is None:
                skipped += 1
                continue
            
            # スケール補正
            depth_scaled = depth * scale
            
            # 無効な深度をマスク
            depth_scaled[depth_scaled < self.depth_min] = 0
            depth_scaled[depth_scaled > self.depth_max] = 0
            
            # タイムスタンプからARCoreポーズを取得
            base_name = Path(img_name).stem
            timestamp = base_name.replace('frame_', '')
            
            if timestamp not in arcore_poses:
                skipped += 1
                continue
            
            arcore_pose = arcore_poses[timestamp]
            
            # GPU Tensor/Imageに変換
            depth_tensor = o3c.Tensor(
                depth_scaled.astype(np.float32),
                dtype=o3c.float32,
                device=self.device
            )
            
            # ImageオブジェクトとしてラップOpen3D T.geometry用）
            depth_image = o3d.t.geometry.Image(depth_tensor)
            
            # 外部パラメータ（ARCoreポーズ）- CPUに置く必要がある
            extrinsic = o3c.Tensor(
                np.linalg.inv(arcore_pose).astype(np.float64),
                dtype=o3c.float64,
                device=cpu_device
            )
            
            try:
                # ブロック座標を計算（Imageオブジェクトを使用）
                frustum_block_coords = vbg.compute_unique_block_coordinates(
                    depth_image, intrinsic_tensor, extrinsic,
                    depth_scale=1.0, depth_max=self.depth_max
                )
                
                # TSDF統合（Imageオブジェクトを使用）
                vbg.integrate(
                    block_coords=frustum_block_coords,
                    depth=depth_image,
                    intrinsic=intrinsic_tensor,
                    extrinsic=extrinsic,
                    depth_scale=1.0,
                    depth_max=self.depth_max
                )
                
                processed += 1
                
            except Exception as e:
                print(f"  ⚠ Error integrating {img_name}: {e}")
                skipped += 1
                continue
            
            # 進捗更新
            if progress_callback and (i + 1) % 50 == 0:
                progress = 25 + int(50 * (i + 1) / total_images)
                progress_callback(
                    progress,
                    f"Integrating: {i+1}/{total_images} ({processed} processed, {skipped} skipped)"
                )
        
        stats['frames_processed'] = processed
        stats['frames_skipped'] = skipped
        
        print(f"  Processed: {processed}, Skipped: {skipped}")
        
        if processed < 10:
            print("Error: Too few frames processed")
            return None, None, stats
        
        if progress_callback:
            progress_callback(80, "Extracting point cloud...")
        
        # 点群抽出
        try:
            pcd = vbg.extract_point_cloud(weight_threshold=self.mesh_weight_threshold)
            pcd_legacy = pcd.to_legacy()
            
            # 点群を保存（標準ファイル名でViewer互換）
            output_dir.mkdir(parents=True, exist_ok=True)
            pcd_path = output_dir / "point_cloud.ply"
            o3d.io.write_point_cloud(str(pcd_path), pcd_legacy)
            
            stats['point_count'] = len(pcd_legacy.points)
            print(f"  Point cloud saved: {stats['point_count']} points")
            
        except Exception as e:
            print(f"Error extracting point cloud: {e}")
            pcd_path = None
        
        if progress_callback:
            progress_callback(90, "Extracting mesh...")
        
        # メッシュ抽出
        mesh_path = None
        try:
            mesh = vbg.extract_triangle_mesh(weight_threshold=self.mesh_weight_threshold)
            mesh_legacy = mesh.to_legacy()
            
            # 法線計算
            mesh_legacy.compute_vertex_normals()
            
            # メッシュを保存（標準ファイル名でViewer互換）
            mesh_path = output_dir / "mesh.ply"
            o3d.io.write_triangle_mesh(str(mesh_path), mesh_legacy)
            
            stats['vertex_count'] = len(mesh_legacy.vertices)
            stats['triangle_count'] = len(mesh_legacy.triangles)
            print(f"  Mesh saved: {stats['vertex_count']} vertices, {stats['triangle_count']} triangles")
            
        except Exception as e:
            print(f"  GPU mesh extraction failed: {e}")
            print(f"  Trying CPU mesh extraction...")
            
            try:
                # CPUに転送してメッシュ抽出
                vbg_cpu = vbg.cpu()
                mesh = vbg_cpu.extract_triangle_mesh(weight_threshold=self.mesh_weight_threshold)
                mesh_legacy = mesh.to_legacy()
                
                mesh_legacy.compute_vertex_normals()
                
                mesh_path = output_dir / "mesh.ply"
                o3d.io.write_triangle_mesh(str(mesh_path), mesh_legacy)
                
                stats['vertex_count'] = len(mesh_legacy.vertices)
                stats['triangle_count'] = len(mesh_legacy.triangles)
                print(f"  Mesh saved (CPU): {stats['vertex_count']} vertices, {stats['triangle_count']} triangles")
                
            except Exception as e2:
                print(f"  CPU mesh extraction also failed: {e2}")
                print(f"  Creating mesh from point cloud using Poisson reconstruction...")
                
                try:
                    # 点群からPoissonでメッシュ生成
                    if pcd_legacy and len(pcd_legacy.points) > 100:
                        pcd_legacy.estimate_normals()
                        mesh_legacy, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                            pcd_legacy, depth=9
                        )
                        
                        mesh_path = output_dir / "mesh.ply"
                        o3d.io.write_triangle_mesh(str(mesh_path), mesh_legacy)
                        
                        stats['vertex_count'] = len(mesh_legacy.vertices)
                        stats['triangle_count'] = len(mesh_legacy.triangles)
                        print(f"  Mesh saved (Poisson): {stats['vertex_count']} vertices, {stats['triangle_count']} triangles")
                        
                except Exception as e3:
                    print(f"  Poisson reconstruction failed: {e3}")
        
        # 変換パラメータを保存
        transform_data = {
            'scale': float(scale),
            'rotation': rotation.tolist(),
            'translation': translation.tolist(),
            'method': 'colmap_depth_integration'
        }
        transform_path = output_dir / "colmap_depth_transform.json"
        with open(transform_path, 'w') as f:
            json.dump(transform_data, f, indent=2)
        
        # ARCore軌跡を保存（Viewer表示用）
        trajectory_data = {
            'coordinate_system': 'arcore',
            'unit': 'meters',
            'count': len(arcore_poses),
            'poses': []
        }
        for timestamp in sorted(arcore_poses.keys()):
            pose = arcore_poses[timestamp]
            trajectory_data['poses'].append({
                'timestamp': timestamp,
                'position': pose[:3, 3].tolist(),
                'rotation': pose[:3, :3].tolist()
            })
        trajectory_path = output_dir / "trajectory.json"
        with open(trajectory_path, 'w') as f:
            json.dump(trajectory_data, f, indent=2)
        print(f"  Trajectory saved: {len(arcore_poses)} poses")
        
        if progress_callback:
            progress_callback(100, "Processing complete")
        
        return pcd_path, mesh_path, stats


def run_colmap_depth_pipeline(
    session_dir: Path,
    output_dir: Path,
    config: dict,
    progress_callback: Callable[[int, str], None] = None
) -> Tuple[Optional[Path], Optional[Path], dict]:
    """
    方法C: スケール補正付きCOLMAP深度統合パイプラインを実行
    
    前提条件:
    - COLMAPのMVS処理が完了していること
    - dense/stereo/depth_maps/*.geometric.bin が存在すること
    
    Args:
        session_dir: セッションデータディレクトリ
        output_dir: 出力ディレクトリ
        config: 設定辞書
        progress_callback: 進捗コールバック
    
    Returns:
        (point_cloud_path, mesh_path, stats)
    """
    pipeline = COLMAPDepthIntegration(config)
    return pipeline.process_session(session_dir, output_dir, progress_callback)
