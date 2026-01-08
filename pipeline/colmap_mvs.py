"""
COLMAP MVS (Multi-View Stereo) Pipeline
ARCore VIOのポーズを使用してSfMをスキップし、Dense MVSで高精度な深度推定を実現
"""

import os
import subprocess
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
import shutil

try:
    import open3d as o3d
    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False
    print("Warning: Open3D not available, COLMAP MVS pipeline may not work correctly")

from utils.arcore_parser import ARCoreDataParser, CameraIntrinsics, Frame
from utils.transforms import rotation_matrix_to_quaternion, arcore_to_open3d_pose


class COLMAPMVSPipeline:
    """
    COLMAP MVSパイプライン
    ARCore VIOのポーズを使用してSfMをスキップし、Dense MVSで高精度な深度推定
    """
    
    def __init__(self, config: Dict[str, Any] = None, gpu_config: Dict[str, Any] = None):
        """
        Args:
            config: 設定辞書
            gpu_config: GPU設定辞書
        """
        self.config = config or {}
        self.gpu_config = gpu_config or {}
        
        # COLMAP設定
        colmap_config = self.config.get('colmap', {})
        self.colmap_path = colmap_config.get('path', 'colmap')  # COLMAP実行ファイルのパス
        
        # MVS設定
        self.max_image_size = colmap_config.get('max_image_size', 1600)  # 画像の最大サイズ（OOM対策で1600に）
        self.patch_match_iterations = colmap_config.get('patch_match_iterations', 3)  # Patch Matchの反復回数
        self.fusion_min_num_pixels = colmap_config.get('fusion_min_num_pixels', 5)  # 融合時の最小ピクセル数
        self.window_radius = colmap_config.get('window_radius', 5)  # Patch Matchのウィンドウ半径
        self.cache_size = colmap_config.get('cache_size', 16)  # キャッシュサイズGB
        
        # GPU設定
        self.use_gpu = self.gpu_config.get('enabled', True) and self.gpu_config.get('use_cuda', True)
    
    def check_colmap_available(self) -> bool:
        """COLMAPが利用可能か確認"""
        try:
            # COLMAPは--versionをサポートしていないため、helpコマンドで確認
            result = subprocess.run(
                [self.colmap_path, "help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # COLMAPが利用可能
                print(f"✓ COLMAP available at: {self.colmap_path}")
                return True
            else:
                print(f"⚠ COLMAP not found or not working: {result.stderr}")
                return False
        except FileNotFoundError:
            print(f"⚠ COLMAP not found at: {self.colmap_path}")
            print("  Install COLMAP: sudo apt-get install colmap")
            return False
        except Exception as e:
            print(f"⚠ Error checking COLMAP: {e}")
            return False
    
    def _get_camera_positions(self, parser: ARCoreDataParser) -> np.ndarray:
        """ARCoreデータからカメラ位置を取得"""
        camera_positions = []
        for frame in parser.frames:
            if frame.pose:
                pose_matrix = frame.pose.to_matrix()
                position = pose_matrix[:3, 3]
                camera_positions.append(position)
        
        if len(camera_positions) == 0:
            return np.array([])
        
        return np.array(camera_positions)
    
    def _compute_colmap_to_arcore_transform(
        self, 
        parser: ARCoreDataParser, 
        colmap_dir: Path
    ) -> dict:
        """COLMAP→ARCore座標変換パラメータを計算"""
        import struct
        from scipy.linalg import orthogonal_procrustes
        
        # ARCoreカメラ位置を取得
        arcore_data = {}
        for frame in parser.frames:
            if frame.pose and frame.image_path:
                pose_matrix = frame.pose.to_matrix()
                position = pose_matrix[:3, 3]
                arcore_data[frame.image_path.name] = position
        
        # COLMAPカメラ位置を取得
        images_bin = colmap_dir / "sparse" / "0" / "images.bin"
        if not images_bin.exists():
            print("Warning: COLMAP images.bin not found")
            return None
        
        colmap_data = {}
        with open(images_bin, "rb") as f:
            num = struct.unpack("Q", f.read(8))[0]
            for _ in range(num):
                image_id = struct.unpack("I", f.read(4))[0]
                qw, qx, qy, qz = struct.unpack("dddd", f.read(32))
                tx, ty, tz = struct.unpack("ddd", f.read(24))
                camera_id = struct.unpack("I", f.read(4))[0]
                name = b""
                while True:
                    char = f.read(1)
                    if char == b"\x00": break
                    name += char
                num_pts = struct.unpack("Q", f.read(8))[0]
                f.read(24 * num_pts)
                
                R = np.array([
                    [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
                    [2*(qx*qy + qz*qw), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qx*qw)],
                    [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx**2 + qy**2)]
                ])
                t = np.array([tx, ty, tz])
                colmap_data[name.decode()] = -R.T @ t
        
        # 共通画像でProcrustes分析
        common_images = sorted(set(arcore_data.keys()) & set(colmap_data.keys()))
        if len(common_images) < 10:
            print(f"Warning: Only {len(common_images)} common images for transform")
            return None
        
        arcore_pts = np.array([arcore_data[img] for img in common_images])
        colmap_pts = np.array([colmap_data[img] for img in common_images])
        
        # 中心化
        arcore_centroid = arcore_pts.mean(axis=0)
        colmap_centroid = colmap_pts.mean(axis=0)
        
        arcore_centered = arcore_pts - arcore_centroid
        colmap_centered = colmap_pts - colmap_centroid
        
        # スケール
        arcore_scale = np.sqrt((arcore_centered ** 2).sum())
        colmap_scale = np.sqrt((colmap_centered ** 2).sum())
        scale = arcore_scale / colmap_scale
        
        # 回転行列
        from scipy.linalg import orthogonal_procrustes
        arcore_normalized = arcore_centered / arcore_scale
        colmap_normalized = colmap_centered / colmap_scale
        R, _ = orthogonal_procrustes(colmap_normalized, arcore_normalized)
        
        print(f"  Coordinate transform: scale={scale:.4f}, {len(common_images)} points")
        
        return {
            'scale': scale,
            'rotation': R,
            'colmap_centroid': colmap_centroid,
            'arcore_centroid': arcore_centroid
        }
    
    def _transform_points_to_arcore(self, points: np.ndarray, transform: dict) -> np.ndarray:
        """COLMAP座標系の点群をARCore座標系に変換"""
        scale = transform['scale']
        R = transform['rotation']
        colmap_centroid = transform['colmap_centroid']
        arcore_centroid = transform['arcore_centroid']
        
        # 変換: p_arcore = scale * R @ (p_colmap - colmap_centroid) + arcore_centroid
        centered = points - colmap_centroid
        transformed = scale * (centered @ R) + arcore_centroid
        return transformed
    
    def run_feature_extractor(
        self,
        session_dir: Path,
        database_path: Path,
        intrinsics: CameraIntrinsics,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPの特徴点抽出を実行"""
        if progress_callback:
            progress_callback(5, "Extracting features from images...")
        
        images_dir = session_dir / "images"
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        # カメラパラメータ: fx,fy,cx,cy
        camera_params = f"{intrinsics.fx},{intrinsics.fy},{intrinsics.cx},{intrinsics.cy}"
        
        try:
            cmd = [
                self.colmap_path, "feature_extractor",
                "--database_path", str(database_path),
                "--image_path", str(images_dir),
                "--ImageReader.camera_model", "PINHOLE",
                "--ImageReader.camera_params", camera_params,
                "--SiftExtraction.max_num_features", "8192"  # デフォルト値（調整可能）
            ]
            # GPUオプションはバージョンによって異なる可能性があるため、条件付きで追加
            if self.use_gpu:
                # CUDA対応版ではGPUが自動的に使用される可能性がある
                # オプションが存在しない場合はエラーになるため、試行錯誤が必要
                pass
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600)
            
            if result.returncode != 0:
                print(f"Error: feature_extractor failed: {result.stderr}")
                return False
            
            print("✓ Features extracted")
            return True
        except Exception as e:
            print(f"Error running feature_extractor: {e}")
            return False
    
    def run_exhaustive_matcher(
        self,
        database_path: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPのexhaustive matcherを実行（全画像ペアをマッチング）"""
        if progress_callback:
            progress_callback(8, "Matching features between images...")
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            cmd = [
                self.colmap_path, "exhaustive_matcher",
                "--database_path", str(database_path)
            ]
            # CUDA対応版ではGPUが自動的に使用される
            # オプションは最小限に（バージョン依存の問題を回避）
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=7200)
            
            if result.returncode != 0:
                print(f"Error: exhaustive_matcher failed: {result.stderr}")
                return False
            
            print("✓ Features matched")
            return True
        except Exception as e:
            print(f"Error running exhaustive_matcher: {e}")
            return False
    
    def run_mapper(
        self,
        session_dir: Path,
        colmap_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPのmapperを実行して完全なsparse reconstructionを構築"""
        if progress_callback:
            progress_callback(10, "Running COLMAP mapper (SfM)...")
        
        images_dir = session_dir / "images"
        database_path = colmap_dir / "database.db"
        sparse_dir = colmap_dir / "sparse"
        sparse_dir.mkdir(parents=True, exist_ok=True)
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            result = subprocess.run([
                self.colmap_path, "mapper",
                "--database_path", str(database_path),
                "--image_path", str(images_dir),
                "--output_path", str(sparse_dir)
            ], capture_output=True, text=True, env=env, timeout=7200)
            
            if result.returncode != 0:
                print(f"Error: mapper failed: {result.stderr}")
                return False
            
            # sparse/0が存在するか確認
            if not (sparse_dir / "0").exists():
                print("Error: mapper did not create sparse/0")
                return False
            
            # 3D点の数を確認
            points_file = sparse_dir / "0" / "points3D.bin"
            if points_file.exists():
                print(f"✓ COLMAP mapper completed (sparse reconstruction created)")
            else:
                print("Warning: No points3D.bin found")
            
            return True
        except subprocess.TimeoutExpired:
            print("Error: mapper timed out (>2 hours)")
            return False
        except Exception as e:
            print(f"Error running mapper: {e}")
            return False
    
    def create_colmap_model_from_arcore_poses(
        self,
        parser: ARCoreDataParser,
        colmap_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """
        ARCore VIOのポーズからCOLMAPモデル（sparse）を作成
        SfMステップをスキップして、直接カメラポーズとカメラパラメータを設定
        """
        if parser.intrinsics is None:
            print("Error: Camera intrinsics not available")
            return False
        
        sparse_dir = colmap_dir / "sparse" / "0"
        sparse_dir.mkdir(parents=True, exist_ok=True)
        
        if progress_callback:
            progress_callback(10, "Creating COLMAP model from ARCore poses...")
        
        # 1. カメラパラメータファイルを作成
        camera_file = sparse_dir / "cameras.txt"
        self._write_cameras_file(camera_file, parser.intrinsics, parser.frames)
        
        # 2. 画像ファイルを作成（画像IDとファイル名のマッピング）
        images_file = sparse_dir / "images.txt"
        self._write_images_file(images_file, parser.frames)
        
        # 3. 点群ファイルを作成（空、または既存の点群を使用）
        points_file = sparse_dir / "points3D.txt"
        self._write_empty_points_file(points_file)
        
        print(f"✓ COLMAP model created from ARCore poses: {len(parser.frames)} images")
        return True
    
    def run_point_triangulator(
        self,
        colmap_dir: Path,
        database_path: Path,
        session_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPのpoint triangulatorを実行（ARCoreポーズを使用して特徴点を3D点に変換）"""
        if progress_callback:
            progress_callback(12, "Triangulating 3D points from features...")
        
        sparse_dir = colmap_dir / "sparse" / "0"
        images_dir = session_dir / "images"  # 元の画像を使用（歪み補正前）
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            result = subprocess.run([
                self.colmap_path, "point_triangulator",
                "--database_path", str(database_path),
                "--image_path", str(images_dir),
                "--input_path", str(sparse_dir),
                "--output_path", str(sparse_dir)
            ], capture_output=True, text=True, env=env, timeout=3600)
            
            if result.returncode != 0:
                print(f"Error: point_triangulator failed: {result.stderr}")
                return False
            
            print("✓ 3D points triangulated")
            return True
        except Exception as e:
            print(f"Error running point_triangulator: {e}")
            return False
    
    def run_bundle_adjuster(
        self,
        colmap_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPのbundle adjusterを実行（ARCoreポーズを初期値として使用）"""
        if progress_callback:
            progress_callback(14, "Running bundle adjustment...")
        
        sparse_dir = colmap_dir / "sparse" / "0"
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            result = subprocess.run([
                self.colmap_path, "bundle_adjuster",
                "--input_path", str(sparse_dir),
                "--output_path", str(sparse_dir),
                "--BundleAdjustment.refine_focal_length", "false",  # 内部パラメータは固定（ARCoreから取得）
                "--BundleAdjustment.refine_principal_point", "false",
                "--BundleAdjustment.refine_extra_params", "false"
            ], capture_output=True, text=True, env=env, timeout=7200)
            
            if result.returncode != 0:
                print(f"Error: bundle_adjuster failed: {result.stderr}")
                return False
            
            print("✓ Bundle adjustment completed")
            return True
        except Exception as e:
            print(f"Error running bundle_adjuster: {e}")
            return False
    
    def _write_cameras_file(self, camera_file: Path, intrinsics: CameraIntrinsics, frames: List[Frame]):
        """COLMAPのcameras.txtファイルを作成"""
        with open(camera_file, 'w') as f:
            f.write("# Camera list with one line of data per camera:\n")
            f.write("#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
            f.write("# Number of cameras: 1\n")
            
            # 最初のフレームから画像サイズを取得
            if frames and frames[0].image_path and frames[0].image_path.exists():
                import cv2
                img = cv2.imread(str(frames[0].image_path))
                if img is not None:
                    height, width = img.shape[:2]
                else:
                    width = intrinsics.width
                    height = intrinsics.height
            else:
                width = intrinsics.width
                height = intrinsics.height
            
            # PINHOLEモデル: fx, fy, cx, cy
            fx = intrinsics.fx
            fy = intrinsics.fy
            cx = intrinsics.cx
            cy = intrinsics.cy
            
            # COLMAP形式: CAMERA_ID MODEL WIDTH HEIGHT fx fy cx cy
            f.write(f"1 PINHOLE {width} {height} {fx} {fy} {cx} {cy}\n")
    
    def _write_images_file(self, images_file: Path, frames: List[Frame]):
        """COLMAPのimages.txtファイルを作成"""
        with open(images_file, 'w') as f:
            f.write("# Image list with two lines of data per image:\n")
            f.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
            f.write("#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
            f.write(f"# Number of images: {len(frames)}\n")
            
            for i, frame in enumerate(frames):
                if frame.pose is None or frame.image_path is None:
                    continue
                
                image_id = i + 1
                image_name = frame.image_path.name
                
                # ARCoreポーズをCOLMAP形式（qw, qx, qy, qz, tx, ty, tz）に変換
                # COLMAPはカメラ→ワールド座標系を期待（OpenCV座標系: Y-down, Z-forward）
                # ARCoreはY-up, -Z-forwardなので、Open3D座標系に変換してから使用
                arcore_pose_matrix = frame.pose.to_matrix()
                
                # ARCore座標系→Open3D座標系（COLMAPも同じOpenCV座標系を使用）
                o3d_pose_matrix = arcore_to_open3d_pose(arcore_pose_matrix)
                
                # 回転行列からクォータニオンに変換
                rotation_matrix = o3d_pose_matrix[:3, :3]
                # utils/transforms.pyの関数を使用（qw, qx, qy, qzの順で返す）
                quat = rotation_matrix_to_quaternion(rotation_matrix)
                
                # 並進ベクトル
                translation = o3d_pose_matrix[:3, 3]
                
                # COLMAP形式: IMAGE_ID qw qx qy qz tx ty tz CAMERA_ID NAME
                f.write(f"{image_id} {quat[0]} {quat[1]} {quat[2]} {quat[3]} "
                       f"{translation[0]} {translation[1]} {translation[2]} 1 {image_name}\n")
                
                # 空のPOINTS2D行（特徴点が無い場合）
                f.write("\n")
    
    def _write_empty_points_file(self, points_file: Path):
        """空のpoints3D.txtファイルを作成"""
        with open(points_file, 'w') as f:
            f.write("# 3D point list with one line of data per point:\n")
            f.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
            f.write("# Number of points: 0\n")
    
    
    def run_image_undistorter(
        self,
        session_dir: Path,
        colmap_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """画像の歪み補正（Dense MVSの準備）"""
        if progress_callback:
            progress_callback(30, "Undistorting images...")
        
        images_dir = session_dir / "images"
        sparse_dir = colmap_dir / "sparse" / "0"
        dense_dir = colmap_dir / "dense"
        dense_dir.mkdir(parents=True, exist_ok=True)
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            result = subprocess.run([
                self.colmap_path, "image_undistorter",
                "--image_path", str(images_dir),
                "--input_path", str(sparse_dir),
                "--output_path", str(dense_dir),
                "--output_type", "COLMAP",
                "--max_image_size", str(self.max_image_size)
            ], capture_output=True, text=True, env=env, timeout=1800)
            
            if result.returncode != 0:
                print(f"Error: image_undistorter failed: {result.stderr}")
                return False
            
            print("✓ Images undistorted")
            return True
        except Exception as e:
            print(f"Error running image_undistorter: {e}")
            return False
    
    def run_patch_match_stereo(
        self,
        colmap_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """Patch Match Stereoで密な深度マップを生成"""
        if progress_callback:
            progress_callback(50, "Running Patch Match Stereo (Dense MVS)...")
        
        dense_dir = colmap_dir / "dense"
        workspace_path = dense_dir
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        # 距離フィルタリング設定を取得（カメラからの距離でフィルタリング）
        colmap_config = self.config.get('colmap', {})
        distance_filter = colmap_config.get('distance_filter', {})
        depth_min = distance_filter.get('min_distance', -1)  # -1 = 無効
        depth_max = distance_filter.get('max_distance', -1)  # -1 = 無効
        
        if distance_filter.get('enable', False):
            print(f"  Depth filter: {depth_min}m - {depth_max}m (from camera)")
        
        try:
            # CUDA対応版がインストールされているため、GPUオプションを有効化
            gpu_options = []
            if self.use_gpu:
                gpu_options = ["--PatchMatchStereo.gpu_index", "0"]
                print("  Using GPU for Patch Match Stereo (CUDA enabled)")
            else:
                print("  Using CPU for Patch Match Stereo (GPU disabled)")
            
            # 深度フィルタリングオプション
            depth_options = []
            if distance_filter.get('enable', False):
                if depth_min > 0:
                    depth_options.extend(["--PatchMatchStereo.depth_min", str(depth_min)])
                if depth_max > 0:
                    depth_options.extend(["--PatchMatchStereo.depth_max", str(depth_max)])
            
            # メモリ節約オプション
            memory_options = [
                "--PatchMatchStereo.window_radius", str(self.window_radius),
                "--PatchMatchStereo.cache_size", str(self.cache_size),
            ]
            
            result = subprocess.run([
                self.colmap_path, "patch_match_stereo",
                "--workspace_path", str(workspace_path),
                "--workspace_format", "COLMAP",
                "--PatchMatchStereo.geom_consistency", "true",
                "--PatchMatchStereo.filter", "true",  # フィルタリングを有効化（必須）
                "--PatchMatchStereo.num_iterations", str(self.patch_match_iterations),
                *gpu_options,
                *depth_options,
                *memory_options
            ], capture_output=True, text=True, env=env, timeout=7200)
            
            if result.returncode != 0:
                print(f"Error: patch_match_stereo failed: {result.stderr}")
                return False
            
            print("✓ Patch Match Stereo completed")
            return True
        except Exception as e:
            print(f"Error running patch_match_stereo: {e}")
            return False
    
    def run_stereo_fusion(
        self,
        colmap_dir: Path,
        output_ply: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """Stereo Fusionで密な点群を生成"""
        if progress_callback:
            progress_callback(80, "Fusing depth maps into point cloud...")
        
        dense_dir = colmap_dir / "dense"
        workspace_path = dense_dir
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            result = subprocess.run([
                self.colmap_path, "stereo_fusion",
                "--workspace_path", str(workspace_path),
                "--workspace_format", "COLMAP",
                "--input_type", "photometric",  # photometricを使用（geometricより点が多い）
                "--output_path", str(output_ply),
                "--StereoFusion.min_num_pixels", str(self.fusion_min_num_pixels)
            ], capture_output=True, text=True, env=env, timeout=3600)
            
            if result.returncode != 0:
                print(f"Error: stereo_fusion failed: {result.stderr}")
                return False
            
            print(f"✓ Point cloud fused: {output_ply}")
            return True
        except Exception as e:
            print(f"Error running stereo_fusion: {e}")
            return False
    
    def run_texture_mapper(
        self,
        colmap_dir: Path,
        mesh_ply: Path,
        textured_ply: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """テクスチャマッピングを実行"""
        if progress_callback:
            progress_callback(90, "Mapping textures...")
        
        dense_dir = colmap_dir / "dense"
        workspace_path = dense_dir
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            result = subprocess.run([
                self.colmap_path, "texture_mapper",
                "--workspace_path", str(workspace_path),
                "--workspace_format", "COLMAP",
                "--input_path", str(mesh_ply),
                "--output_path", str(textured_ply)
            ], capture_output=True, text=True, env=env, timeout=1800)
            
            if result.returncode != 0:
                print(f"Warning: texture_mapper failed: {result.stderr}")
                return False
            
            print(f"✓ Texture mapped: {textured_ply}")
            return True
        except Exception as e:
            print(f"Warning running texture_mapper: {e}")
            return False
    
    def process_session(
        self,
        parser: ARCoreDataParser,
        session_dir: Path,
        result_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> Tuple[Optional[o3d.geometry.PointCloud], Optional[o3d.geometry.TriangleMesh]]:
        """
        セッション全体を処理
        
        Args:
            parser: ARCoreデータパーサー
            session_dir: セッションディレクトリ
            result_dir: 結果ディレクトリ
            progress_callback: 進捗コールバック
            
        Returns:
            (点群, メッシュ) のタプル
        """
        if not self.check_colmap_available():
            return None, None
        
        if parser.intrinsics is None:
            print("Error: Camera intrinsics not available")
            return None, None
        
        colmap_dir = session_dir / "colmap"
        colmap_dir.mkdir(parents=True, exist_ok=True)
        database_path = colmap_dir / "database.db"
        
        # Step 1: 特徴点抽出
        if not self.run_feature_extractor(session_dir, database_path, parser.intrinsics, progress_callback):
            return None, None
        
        # Step 2: 特徴点マッチング
        if not self.run_exhaustive_matcher(database_path, progress_callback):
            return None, None
        
        # Step 3: COLMAPのmapperを実行してsparse reconstructionを構築
        # ARCoreポーズは使用せず、完全なSfMを実行して3D点を生成
        if not self.run_mapper(session_dir, colmap_dir, progress_callback):
            print("Warning: COLMAP mapper failed, trying with ARCore poses...")
            # フォールバック: ARCoreポーズを使用
            if not self.create_colmap_model_from_arcore_poses(parser, colmap_dir, progress_callback):
                return None, None
        
        # Step 6: 画像の歪み補正
        if not self.run_image_undistorter(session_dir, colmap_dir, progress_callback):
            return None, None
        
        # Step 7: Patch Match Stereoで密な深度マップを生成
        if not self.run_patch_match_stereo(colmap_dir, progress_callback):
            return None, None
        
        # Step 8: Stereo Fusionで密な点群を生成
        fused_ply = colmap_dir / "dense" / "fused.ply"
        if not self.run_stereo_fusion(colmap_dir, fused_ply, progress_callback):
            return None, None
        
        if not fused_ply.exists():
            print("Error: Fused point cloud file not found")
            return None, None
        
        # Step 9: 点群を読み込んでOpen3D形式に変換
        if progress_callback:
            progress_callback(85, "Loading point cloud...")
        
        pcd = o3d.io.read_point_cloud(str(fused_ply))
        if len(pcd.points) == 0:
            print("Error: Point cloud is empty")
            return None, None
        
        print(f"✓ Loaded point cloud: {len(pcd.points)} points")
        
        # 後処理1: 座標変換 + カメラからの距離でフィルタリング
        colmap_config = self.config.get('colmap', {})
        distance_filter = colmap_config.get('distance_filter', {})
        
        if distance_filter.get('enable', False):
            max_distance = distance_filter.get('max_distance', 3.0)
            min_distance = distance_filter.get('min_distance', 0.1)
            
            if progress_callback:
                progress_callback(84, "Computing coordinate transform...")
            
            # COLMAP→ARCore座標変換を計算
            transform = self._compute_colmap_to_arcore_transform(parser, colmap_dir)
            
            if transform is not None:
                if progress_callback:
                    progress_callback(85, f"Filtering points: {min_distance}m - {max_distance}m from cameras...")
                
                points = np.asarray(pcd.points)
                colors = np.asarray(pcd.colors) if pcd.has_colors() else None
                normals = np.asarray(pcd.normals) if pcd.has_normals() else None
                
                # 点群をARCore座標系に変換
                points_arcore = self._transform_points_to_arcore(points, transform)
                
                # ARCoreカメラ位置を取得
                camera_positions = self._get_camera_positions(parser)
                
                if len(camera_positions) > 0:
                    # 各点から最近傍カメラまでの距離を計算
                    from scipy.spatial import cKDTree
                    tree = cKDTree(camera_positions)
                    distances, _ = tree.query(points_arcore)
                    
                    # フィルタリング
                    mask = (distances >= min_distance) & (distances <= max_distance)
                    
                    filtered_points = points_arcore[mask]
                    pcd_filtered = o3d.geometry.PointCloud()
                    pcd_filtered.points = o3d.utility.Vector3dVector(filtered_points)
                    
                    if colors is not None and len(colors) == len(points):
                        pcd_filtered.colors = o3d.utility.Vector3dVector(colors[mask])
                    if normals is not None and len(normals) == len(points):
                        # 法線も変換（回転のみ）
                        normals_transformed = normals @ transform['rotation']
                        pcd_filtered.normals = o3d.utility.Vector3dVector(normals_transformed[mask])
                    
                    print(f"  Camera distance filter ({min_distance}-{max_distance}m): {len(pcd.points):,} → {len(pcd_filtered.points):,} points")
                    print(f"  Coordinate system: ARCore")
                    pcd = pcd_filtered
                else:
                    print("  Warning: No camera positions, using original points")
            else:
                print("  Warning: Transform failed, using original points")
        
        # 後処理2: 統計的外れ値除去
        if progress_callback:
            progress_callback(86, "Removing statistical outliers...")
        
        original_count = len(pcd.points)
        pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        print(f"  Statistical outlier removal: {original_count:,} → {len(pcd.points):,} points")
        
        # Step 10: 点群からメッシュを生成（Poisson reconstruction）
        if progress_callback:
            progress_callback(87, "Generating mesh from point cloud...")
        
        mesh_config = self.config.get('mesh', {})
        poisson_config = mesh_config.get('poisson', {})
        depth = poisson_config.get('depth', 10)
        
        try:
            mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=depth
            )
            
            # 密度の低い頂点を除去
            density_threshold_percentile = poisson_config.get('density_threshold_percentile', 5)
            if density_threshold_percentile > 0:
                vertices_to_remove = densities < np.quantile(densities, density_threshold_percentile / 100.0)
                mesh.remove_vertices_by_mask(vertices_to_remove)
            
            if len(mesh.triangles) == 0:
                print("Warning: Mesh has no triangles")
                return pcd, None
            
            print(f"✓ Generated mesh: {len(mesh.vertices)} vertices, {len(mesh.triangles)} triangles")
            
            # メッシュ品質改善
            mesh_config = self.config.get('mesh', {})
            
            # 1. スムージング
            smoothing_config = mesh_config.get('smoothing', {})
            if smoothing_config.get('enable', True):
                iterations = smoothing_config.get('iterations', 5)
                lambda_filter = smoothing_config.get('lambda_filter', 0.5)
                mesh = mesh.filter_smooth_laplacian(iterations, lambda_filter)
                print(f"✓ Mesh smoothed (laplacian, {iterations} iterations)")
            
            # 2. 法線再計算
            mesh.compute_vertex_normals()
            
            # 3. 小さな連結成分を除去（ノイズ除去）
            triangle_clusters, cluster_n_triangles, cluster_area = mesh.cluster_connected_triangles()
            triangle_clusters = np.asarray(triangle_clusters)
            cluster_n_triangles = np.asarray(cluster_n_triangles)
            
            # 最大クラスタの10%未満のクラスタを除去
            if len(cluster_n_triangles) > 1:
                max_cluster_size = cluster_n_triangles.max()
                threshold = max_cluster_size * 0.1
                triangles_to_remove = cluster_n_triangles[triangle_clusters] < threshold
                mesh.remove_triangles_by_mask(triangles_to_remove)
                mesh.remove_unreferenced_vertices()
                print(f"✓ Small components removed (kept clusters > {threshold:.0f} triangles)")
            
            print("✓ Mesh quality improved")
            
            # Step 11: テクスチャマッピング（オプション）
            mesh_ply = result_dir / "mesh_before_texture.ply"
            o3d.io.write_triangle_mesh(str(mesh_ply), mesh)
            
            textured_ply = result_dir / "mesh_textured.ply"
            if self.run_texture_mapper(colmap_dir, mesh_ply, textured_ply, progress_callback):
                if textured_ply.exists():
                    mesh_textured = o3d.io.read_triangle_mesh(str(textured_ply))
                    if len(mesh_textured.triangles) > 0:
                        mesh = mesh_textured
                        print("✓ Texture mapping applied")
            
            return pcd, mesh
            
        except Exception as e:
            print(f"Error generating mesh: {e}")
            import traceback
            traceback.print_exc()
            return pcd, None
