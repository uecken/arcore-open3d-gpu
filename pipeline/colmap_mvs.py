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
    
    def _find_largest_sparse_model(self, sparse_dir: Path) -> str:
        """最大のsparseモデルを見つける（画像数が最も多いもの）"""
        if not sparse_dir.exists():
            return "0"
        
        largest_model = "0"
        largest_size = 0
        
        for model_dir in sparse_dir.iterdir():
            if model_dir.is_dir() and model_dir.name.isdigit():
                # .bin または .txt ファイルを探す
                images_file = model_dir / "images.bin"
                if not images_file.exists():
                    images_file = model_dir / "images.txt"
                
                if images_file.exists():
                    size = images_file.stat().st_size
                    if size > largest_size:
                        largest_size = size
                        largest_model = model_dir.name
        
        if largest_model != "0":
            print(f"  Using largest sparse model: {largest_model} ({largest_size:,} bytes)")
        
        return largest_model
    
    def _read_colmap_images(self, model_dir: Path) -> dict:
        """COLMAPのimages.bin または images.txt からカメラ位置を読み込む"""
        import struct
        
        colmap_data = {}
        
        # まず .bin ファイルを試す
        images_bin = model_dir / "images.bin"
        if images_bin.exists():
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
            return colmap_data
        
        # .txt ファイルを試す
        images_txt = model_dir / "images.txt"
        if images_txt.exists():
            with open(images_txt, 'r') as f:
                lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('#') or not line:
                    i += 1
                    continue
                
                # IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
                parts = line.split()
                if len(parts) >= 10:
                    qw, qx, qy, qz = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                    tx, ty, tz = float(parts[5]), float(parts[6]), float(parts[7])
                    name = parts[9]
                    
                    R = np.array([
                        [1 - 2*(qy**2 + qz**2), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
                        [2*(qx*qy + qz*qw), 1 - 2*(qx**2 + qz**2), 2*(qy*qz - qx*qw)],
                        [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx**2 + qy**2)]
                    ])
                    t = np.array([tx, ty, tz])
                    colmap_data[name] = -R.T @ t
                    
                    # 次の行（POINTS2D）をスキップ
                    i += 2
                else:
                    i += 1
            
            return colmap_data
        
        return None
    
    def _compute_colmap_to_arcore_transform(
        self, 
        parser: ARCoreDataParser, 
        colmap_dir: Path
    ) -> dict:
        """COLMAP→ARCore座標変換パラメータを計算（ドリフト耐性あり）"""
        import struct
        from scipy.linalg import orthogonal_procrustes
        
        # ARCoreカメラ位置を取得
        arcore_data = {}
        for frame in parser.frames:
            if frame.pose and frame.image_path:
                pose_matrix = frame.pose.to_matrix()
                position = pose_matrix[:3, 3]
                arcore_data[frame.image_path.name] = position
        
        # COLMAPカメラ位置を取得（最大モデルを使用）
        sparse_dir = colmap_dir / "sparse"
        model_id = self._find_largest_sparse_model(sparse_dir)
        colmap_data = self._read_colmap_images(sparse_dir / model_id)
        
        if colmap_data is None or len(colmap_data) == 0:
            print("Warning: No COLMAP images found")
            return None
        
        # 共通画像でProcrustes分析
        common_images = sorted(set(arcore_data.keys()) & set(colmap_data.keys()))
        if len(common_images) < 10:
            print(f"Warning: Only {len(common_images)} common images for transform")
            return None
        
        arcore_pts = np.array([arcore_data[img] for img in common_images])
        colmap_pts = np.array([colmap_data[img] for img in common_images])
        
        def compute_procrustes(src_pts, tgt_pts):
            """Procrustes分析でscale, R, centroids を計算"""
            src_centroid = src_pts.mean(axis=0)
            tgt_centroid = tgt_pts.mean(axis=0)
            
            src_centered = src_pts - src_centroid
            tgt_centered = tgt_pts - tgt_centroid
            
            src_scale = np.sqrt((src_centered ** 2).sum())
            tgt_scale = np.sqrt((tgt_centered ** 2).sum())
            scale = tgt_scale / src_scale
            
            src_normalized = src_centered / src_scale
            tgt_normalized = tgt_centered / tgt_scale
            R, _ = orthogonal_procrustes(src_normalized, tgt_normalized)
            
            return scale, R, src_centroid, tgt_centroid
        
        def apply_transform(pts, scale, R, src_c, tgt_c):
            return scale * ((pts - src_c) @ R) + tgt_c
        
        # 初回: 全データでProcrustes
        scale, R, colmap_centroid, arcore_centroid = compute_procrustes(colmap_pts, arcore_pts)
        transformed = apply_transform(colmap_pts, scale, R, colmap_centroid, arcore_centroid)
        errors = np.linalg.norm(transformed - arcore_pts, axis=1)
        
        initial_mean_error = errors.mean()
        print(f"  Initial transform: scale={scale:.4f}, mean_error={initial_mean_error:.4f}m")
        
        # 反復的外れ値除去（RANSAC風）
        max_iterations = 3
        for iteration in range(max_iterations):
            # 誤差の75パーセンタイル以下をinlierとする
            threshold = np.percentile(errors, 75)
            inliers = errors < threshold
            inlier_count = inliers.sum()
            
            if inlier_count < 10:
                print(f"  Warning: Too few inliers ({inlier_count}), stopping refinement")
                break
            
            # inlierのみで再計算
            scale, R, colmap_centroid, arcore_centroid = compute_procrustes(
                colmap_pts[inliers], arcore_pts[inliers]
            )
            transformed = apply_transform(colmap_pts, scale, R, colmap_centroid, arcore_centroid)
            errors = np.linalg.norm(transformed - arcore_pts, axis=1)
            
            new_mean_error = errors.mean()
            if iteration > 0:
                print(f"  Refinement {iteration+1}: inliers={inlier_count}, mean_error={new_mean_error:.4f}m")
            
            # 改善が小さくなったら終了
            if abs(initial_mean_error - new_mean_error) < 0.01:
                break
            initial_mean_error = new_mean_error
        
        # 最終誤差を報告
        final_mean_error = errors.mean()
        final_median_error = np.median(errors)
        print(f"  Final transform: scale={scale:.4f}, mean_error={final_mean_error:.4f}m, median={final_median_error:.4f}m")
        
        # ドリフト警告
        n_bins = 4
        bin_size = len(common_images) // n_bins
        drift_detected = False
        for i in range(n_bins):
            start = i * bin_size
            end = (i + 1) * bin_size if i < n_bins - 1 else len(common_images)
            bin_error = errors[start:end].mean()
            if i == n_bins - 1 and bin_error > final_mean_error * 1.5:
                drift_detected = True
        
        if drift_detected:
            print(f"  ⚠️ Warning: Temporal drift detected. Later frames have higher error.")
        
        return {
            'scale': scale,
            'rotation': R,
            'colmap_centroid': colmap_centroid,
            'arcore_centroid': arcore_centroid,
            'mean_error': final_mean_error,
            'median_error': final_median_error
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
    
    def _save_trajectory(self, parser: ARCoreDataParser, result_dir: Path) -> int:
        """ARCoreカメラ軌跡を保存（点群と同じ座標系、回転情報付き）"""
        import json
        
        poses = []
        prev_pos = None
        
        for frame in parser.frames:
            if frame.pose:
                pose_matrix = frame.pose.to_matrix()
                position = pose_matrix[:3, 3]
                
                # 重複を除去（0.001m以上移動した場合のみ追加）
                if prev_pos is None or np.linalg.norm(position - prev_pos) > 0.001:
                    # ARCore回転（クォータニオン）を取得
                    quat = frame.pose.quaternion  # [qx, qy, qz, qw]
                    
                    poses.append({
                        "position": {
                            "x": float(position[0]),
                            "y": float(position[1]),
                            "z": float(position[2])
                        },
                        "rotation": [float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])],
                        "timestamp": frame.timestamp if hasattr(frame, 'timestamp') else None
                    })
                    prev_pos = position
        
        # 保存
        trajectory_path = result_dir / "trajectory.json"
        with open(trajectory_path, 'w') as f:
            json.dump({
                "poses": poses, 
                "count": len(poses), 
                "coordinate_system": "arcore",
                "rotation_format": "quaternion_xyzw"
            }, f, indent=2)
        
        print(f"✓ Trajectory saved: {len(poses)} poses (with rotation)")
        return len(poses)
    
    def _insert_pose_priors(
        self,
        parser: ARCoreDataParser,
        database_path: Path
    ) -> int:
        """ARCoreのポーズをpose_priorsテーブルに挿入（方式2）
        
        COLMAPのpose_prior_mapperで使用するための位置拘束を設定
        """
        import sqlite3
        import struct
        
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        # 既存のpose_priorsをクリア
        cursor.execute("DELETE FROM pose_priors")
        
        # 画像名とimage_id/data_idのマッピングを取得
        cursor.execute("""
            SELECT i.image_id, i.name, fd.data_id, fd.sensor_id
            FROM images i
            JOIN frame_data fd ON fd.data_id = i.image_id
        """)
        image_mapping = {}
        for row in cursor.fetchall():
            # frame_79274840173634.jpg → 79274840173634
            timestamp = row[1].replace('frame_', '').replace('.jpg', '')
            image_mapping[timestamp] = {
                'image_id': row[0],
                'data_id': row[2],
                'sensor_id': row[3]
            }
        
        # ARCoreポーズを取得
        arcore_poses = {}
        for frame in parser.frames:
            if frame.pose:
                ts = str(frame.timestamp) if hasattr(frame, 'timestamp') else None
                if ts:
                    pose_matrix = frame.pose.to_matrix()
                    position = pose_matrix[:3, 3]
                    arcore_poses[ts] = position
        
        inserted = 0
        for ts, position in arcore_poses.items():
            if ts not in image_mapping:
                continue
            
            mapping = image_mapping[ts]
            
            # ARCore座標系 → COLMAP座標系の変換
            # ARCore: Y軸上向き、Z軸後方
            # COLMAP: Y軸下向き、Z軸前方
            colmap_position = [
                float(position[0]),      # X: 同じ
                float(-position[1]),     # Y: 反転
                float(-position[2])      # Z: 反転
            ]
            
            # 位置をBLOB形式に変換 (3x float64)
            position_blob = struct.pack('ddd', *colmap_position)
            
            # 共分散行列（単位行列 * σ^2）
            # config.yamlの設定を使用
            pose_prior_config = self.config.get('colmap', {}).get('pose_prior', {})
            std_x = pose_prior_config.get('position_std_x', 0.1)
            std_y = pose_prior_config.get('position_std_y', 0.1)
            std_z = pose_prior_config.get('position_std_z', 0.1)
            
            cov = np.array([
                [std_x**2, 0, 0],
                [0, std_y**2, 0],
                [0, 0, std_z**2]
            ])
            cov_blob = struct.pack('d'*9, *cov.flatten())
            
            # 重力方向（COLMAP座標系でY軸下向き）
            gravity = [0.0, 1.0, 0.0]
            gravity_blob = struct.pack('ddd', *gravity)
            
            # coordinate_system: 0 = UNDEFINED (GPS以外)
            coordinate_system = 0
            
            cursor.execute("""
                INSERT INTO pose_priors 
                (corr_data_id, corr_sensor_id, corr_sensor_type, 
                 position, position_covariance, gravity, coordinate_system)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                mapping['data_id'],
                mapping['sensor_id'],
                0,  # sensor_type: 0 = IMAGE
                position_blob,
                cov_blob,
                gravity_blob,
                coordinate_system
            ))
            inserted += 1
        
        conn.commit()
        conn.close()
        
        print(f"✓ Pose priors inserted: {inserted} poses")
        return inserted
    
    def run_pose_prior_mapper(
        self,
        session_dir: Path,
        colmap_dir: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPのpose_prior_mapperを実行（方式2）
        
        ARCoreのポーズを拘束条件としてSfMを実行
        """
        if progress_callback:
            progress_callback(10, "Running COLMAP pose_prior_mapper (SfM with ARCore constraints)...")
        
        images_dir = session_dir / "images"
        database_path = colmap_dir / "database.db"
        sparse_dir = colmap_dir / "sparse"
        sparse_dir.mkdir(parents=True, exist_ok=True)
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            import re
            import os as os_module
            
            num_threads = os_module.cpu_count() or 4
            
            # pose_prior設定を取得
            pose_prior_config = self.config.get('colmap', {}).get('pose_prior', {})
            std_x = pose_prior_config.get('position_std_x', 0.1)
            std_y = pose_prior_config.get('position_std_y', 0.1)
            std_z = pose_prior_config.get('position_std_z', 0.1)
            use_robust = pose_prior_config.get('use_robust_loss', True)
            
            # GPU/マルチスレッドオプション
            gpu_options = []
            if self.use_gpu:
                gpu_options = [
                    "--Mapper.ba_use_gpu", "1",
                    "--Mapper.ba_gpu_index", "0",
                ]
                print(f"  Using GPU for Bundle Adjustment")
            
            cmd = [
                self.colmap_path, "pose_prior_mapper",
                "--database_path", str(database_path),
                "--image_path", str(images_dir),
                "--output_path", str(sparse_dir),
                "--Mapper.num_threads", str(num_threads),
                "--prior_position_std_x", str(std_x),
                "--prior_position_std_y", str(std_y),
                "--prior_position_std_z", str(std_z),
                "--use_robust_loss_on_prior_position", "1" if use_robust else "0",
                "--overwrite_priors_covariance", "1",  # config.yamlの設定を使用
                *gpu_options
            ]
            print(f"  Using {num_threads} CPU threads for pose_prior_mapper")
            print(f"  Prior position std: ({std_x}, {std_y}, {std_z})m")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1
            )
            
            last_progress = 10
            registered_images = 0
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                reg_match = re.search(r'Registering image #(\d+)', line)
                if reg_match:
                    registered_images = int(reg_match.group(1))
                    progress = 10 + min(int(registered_images / 50), 20)
                    if progress > last_progress and progress_callback:
                        progress_callback(progress, f"SfM (with priors): {registered_images} images")
                        last_progress = progress
                    if registered_images % 50 == 0:
                        print(f"  SfM (with priors): {registered_images} images registered")
                
                if "Bundle adjustment" in line:
                    if progress_callback:
                        progress_callback(25, "Bundle adjustment with pose priors...")
                    print("  Bundle adjustment with pose priors...")
            
            process.wait()
            
            if process.returncode != 0:
                print(f"Error: pose_prior_mapper failed (exit code {process.returncode})")
                return False
            
            # sparseモデルが存在するか確認
            model_dirs = [d for d in sparse_dir.iterdir() if d.is_dir() and d.name.isdigit()]
            if not model_dirs:
                print("Error: pose_prior_mapper did not create any sparse model")
                return False
            
            largest_model = self._find_largest_sparse_model(sparse_dir)
            print(f"✓ SfM completed with pose priors (model: {largest_model})")
            
            if progress_callback:
                progress_callback(30, "SfM with pose priors completed")
            
            return True
            
        except subprocess.TimeoutExpired:
            print("Error: pose_prior_mapper timed out")
            process.kill()
            return False
        except Exception as e:
            print(f"Error running pose_prior_mapper: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
            # GPUオプション（正しいオプション名: FeatureExtraction.use_gpu）
            gpu_options = []
            if self.use_gpu:
                gpu_options = [
                    "--FeatureExtraction.use_gpu", "1",
                    "--FeatureExtraction.gpu_index", "0",
                ]
                print("  Using GPU for feature extraction")
            
            cmd = [
                self.colmap_path, "feature_extractor",
                "--database_path", str(database_path),
                "--image_path", str(images_dir),
                "--ImageReader.camera_model", "PINHOLE",
                "--ImageReader.camera_params", camera_params,
                "--SiftExtraction.max_num_features", "8192",
                *gpu_options
            ]
            
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
            # GPUオプション（正しいオプション名: FeatureMatching.use_gpu）
            gpu_options = []
            if self.use_gpu:
                gpu_options = [
                    "--FeatureMatching.use_gpu", "1",
                    "--FeatureMatching.gpu_index", "0",
                ]
                print("  Using GPU for feature matching")
            
            cmd = [
                self.colmap_path, "exhaustive_matcher",
                "--database_path", str(database_path),
                *gpu_options
            ]
            
            # リアルタイム進捗表示のためにPopenを使用
            import re
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                env=env,
                bufsize=1
            )
            
            last_progress = 8
            total_pairs = None
            matched_pairs = 0
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                # 進捗パターンを検出: "Matching block [X/Y]" または "Matching image pairs"
                block_match = re.search(r'Matching block \[(\d+)/(\d+)\]', line)
                if block_match:
                    current = int(block_match.group(1))
                    total = int(block_match.group(2))
                    # 8-10%の範囲で進捗を計算
                    progress = 8 + int((current / total) * 2)
                    if progress > last_progress and progress_callback:
                        progress_callback(progress, f"Feature matching: block {current}/{total}")
                        last_progress = progress
                        print(f"  Feature matching: block {current}/{total}")
                
                # 画像ペアマッチング進捗
                pair_match = re.search(r'Matching image #(\d+)', line)
                if pair_match:
                    img_num = int(pair_match.group(1))
                    if img_num % 50 == 0:  # 50枚ごとに更新
                        print(f"  Matching image #{img_num}")
            
            process.wait()
            
            if process.returncode != 0:
                print(f"Error: exhaustive_matcher failed (exit code {process.returncode})")
                return False
            
            print("✓ Features matched (exhaustive)")
            if progress_callback:
                progress_callback(10, "Feature matching completed")
            return True
        except subprocess.TimeoutExpired:
            print("Error: exhaustive_matcher timed out (>2 hours)")
            process.kill()
            return False
        except Exception as e:
            print(f"Error running exhaustive_matcher: {e}")
            return False
    
    def run_sequential_matcher(
        self,
        database_path: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """COLMAPのsequential matcherを実行（隣接画像のみマッチング、高速）"""
        if progress_callback:
            progress_callback(8, "Matching features (sequential)...")
        
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        try:
            # 設定を取得
            colmap_config = self.config.get('colmap', {})
            seq_config = colmap_config.get('sequential_matching', {})
            overlap = seq_config.get('overlap', 10)
            quadratic_overlap = seq_config.get('quadratic_overlap', True)
            loop_detection = seq_config.get('loop_detection', False)
            
            # GPUオプション
            gpu_options = []
            if self.use_gpu:
                gpu_options = [
                    "--SiftMatching.use_gpu", "1",
                    "--SiftMatching.gpu_index", "0",
                ]
                print("  Using GPU for feature matching")
            
            cmd = [
                self.colmap_path, "sequential_matcher",
                "--database_path", str(database_path),
                "--SequentialMatching.overlap", str(overlap),
                "--SequentialMatching.quadratic_overlap", "1" if quadratic_overlap else "0",
                "--SequentialMatching.loop_detection", "1" if loop_detection else "0",
                *gpu_options
            ]
            
            print(f"  Sequential matcher: overlap={overlap}, quadratic={quadratic_overlap}")
            
            import re
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True, 
                env=env,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                # 進捗出力（デバッグ用）
                if "Matching" in line and "image" in line.lower():
                    print(f"  {line[:60]}")
            
            process.wait()
            
            if process.returncode != 0:
                print(f"Error: sequential_matcher failed (exit code {process.returncode})")
                return False
            
            print("✓ Features matched (sequential)")
            if progress_callback:
                progress_callback(10, "Feature matching completed")
            return True
        except subprocess.TimeoutExpired:
            print("Error: sequential_matcher timed out")
            process.kill()
            return False
        except Exception as e:
            print(f"Error running sequential_matcher: {e}")
            return False
    
    def run_feature_matcher(
        self,
        database_path: Path,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """設定に応じたmatcherを実行"""
        colmap_config = self.config.get('colmap', {})
        matcher_type = colmap_config.get('matcher', 'exhaustive')
        
        print(f"  Matcher type: {matcher_type}")
        
        if matcher_type == 'sequential':
            return self.run_sequential_matcher(database_path, progress_callback)
        else:
            return self.run_exhaustive_matcher(database_path, progress_callback)
    
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
            import re
            import os as os_module
            
            # CPUスレッド数を取得（利用可能なコア数）
            num_threads = os_module.cpu_count() or 4
            
            # GPU/マルチスレッドオプションを追加
            gpu_options = []
            if self.use_gpu:
                gpu_options = [
                    "--Mapper.ba_use_gpu", "1",  # Bundle AdjustmentにGPUを使用
                    "--Mapper.ba_gpu_index", "0",
                ]
                print(f"  Using GPU for Bundle Adjustment")
            
            cmd = [
                self.colmap_path, "mapper",
                "--database_path", str(database_path),
                "--image_path", str(images_dir),
                "--output_path", str(sparse_dir),
                "--Mapper.num_threads", str(num_threads),  # マルチスレッド
                *gpu_options
            ]
            print(f"  Using {num_threads} CPU threads for mapper")
            
            # リアルタイム進捗表示のためにPopenを使用
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1
            )
            
            last_progress = 10
            registered_images = 0
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                # 登録済み画像数: "Registering image #X (Y)"
                reg_match = re.search(r'Registering image #(\d+)', line)
                if reg_match:
                    registered_images = int(reg_match.group(1))
                    # 10-30%の範囲で進捗を計算（推定）
                    # 画像枚数が不明なので、最大1000枚と仮定
                    progress = 10 + min(int(registered_images / 50), 20)
                    if progress > last_progress and progress_callback:
                        progress_callback(progress, f"SfM: {registered_images} images registered")
                        last_progress = progress
                    if registered_images % 50 == 0:
                        print(f"  SfM: {registered_images} images registered")
                
                # バンドル調整: "Bundle adjustment"
                if "Bundle adjustment" in line:
                    if progress_callback:
                        progress_callback(25, "Bundle adjustment...")
                    print("  Bundle adjustment...")
            
            process.wait()
            
            if process.returncode != 0:
                print(f"Error: mapper failed (exit code {process.returncode})")
                return False
            
            # sparseモデルが存在するか確認
            model_dirs = [d for d in sparse_dir.iterdir() if d.is_dir() and d.name.isdigit()]
            if not model_dirs:
                print("Error: mapper did not create any sparse model")
                return False
            
            # 最大モデルを特定
            largest_model = self._find_largest_sparse_model(sparse_dir)
            
            # 3D点の数を確認
            points_file = sparse_dir / largest_model / "points3D.bin"
            if points_file.exists():
                print(f"✓ COLMAP mapper completed (sparse reconstruction created)")
            else:
                print("Warning: No points3D.bin found")
            
            return True
        except subprocess.TimeoutExpired:
            print("Error: mapper timed out (>2 hours)")
            process.kill()
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
        # 最大のsparseモデルを使用
        sparse_base = colmap_dir / "sparse"
        model_id = self._find_largest_sparse_model(sparse_base)
        sparse_dir = sparse_base / model_id
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
            
            import re
            cmd = [
                self.colmap_path, "patch_match_stereo",
                "--workspace_path", str(workspace_path),
                "--workspace_format", "COLMAP",
                "--PatchMatchStereo.geom_consistency", "true",
                "--PatchMatchStereo.filter", "true",
                "--PatchMatchStereo.num_iterations", str(self.patch_match_iterations),
                *gpu_options,
                *depth_options,
                *memory_options
            ]
            
            # リアルタイム進捗表示のためにPopenを使用
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1
            )
            
            last_progress = 50
            total_images = None
            
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                
                # 画像処理進捗: "Processing view X / Y"
                view_match = re.search(r'Processing view (\d+) / (\d+)', line)
                if view_match:
                    current = int(view_match.group(1))
                    total = int(view_match.group(2))
                    total_images = total
                    # 50-80%の範囲で進捗を計算
                    progress = 50 + int((current / total) * 30)
                    if progress > last_progress and progress_callback:
                        progress_callback(progress, f"Patch Match: {current}/{total} images")
                        last_progress = progress
                    if current % 20 == 0 or current == total:
                        print(f"  Patch Match: {current}/{total} images")
            
            process.wait()
            
            if process.returncode != 0:
                print(f"Error: patch_match_stereo failed (exit code {process.returncode})")
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
        
        # 処理モードの確認
        colmap_config = self.config.get('colmap', {})
        use_arcore_poses = colmap_config.get('use_arcore_poses', False)
        use_pose_priors = colmap_config.get('use_pose_priors', False)
        
        if use_arcore_poses:
            # ARCoreポーズを直接使用（SfMスキップモード）- 非推奨
            print("\n=== ARCore Poses Mode (Legacy) ===")
            print("  Using ARCore VIO poses directly (skipping COLMAP SfM)")
            
            # Step 1: 特徴点抽出（Patch Match Stereoに必要）
            if not self.run_feature_extractor(session_dir, database_path, parser.intrinsics, progress_callback):
                return None, None
            
            # Step 2: 特徴点マッチング（3D点の三角測量に必要）
            if progress_callback:
                progress_callback(8, "Matching features for triangulation...")
            if not self.run_feature_matcher(database_path, progress_callback):
                return None, None
            
            # Step 3: ARCoreポーズからCOLMAPモデルを作成
            if progress_callback:
                progress_callback(12, "Creating COLMAP model from ARCore poses...")
            if not self.create_colmap_model_from_arcore_poses(parser, colmap_dir, progress_callback):
                print("Error: Failed to create COLMAP model from ARCore poses")
                return None, None
            
            print("  ✓ ARCore poses converted to COLMAP format")
            
            # Step 4: 3D点を三角測量（Patch Match Stereoのdepth range推定に必要）
            if progress_callback:
                progress_callback(15, "Triangulating 3D points...")
            if not self.run_point_triangulator(colmap_dir, database_path, session_dir, progress_callback):
                print("Warning: Point triangulation failed, Patch Match Stereo may not work correctly")
            else:
                print("  ✓ 3D points triangulated")
        
        elif use_pose_priors:
            # 方式2: ARCoreポーズをpose_priorsとして使用
            print("\n=== COLMAP SfM with Pose Priors (Method 2) ===")
            print("  Using ARCore positions as constraints for SfM")
            
            # Step 1: 特徴点抽出
            if not self.run_feature_extractor(session_dir, database_path, parser.intrinsics, progress_callback):
                return None, None
            
            # Step 2: ARCoreポーズをpose_priorsテーブルに挿入
            if progress_callback:
                progress_callback(7, "Inserting ARCore pose priors...")
            inserted = self._insert_pose_priors(parser, database_path)
            if inserted == 0:
                print("Warning: No pose priors inserted, falling back to standard SfM")
                use_pose_priors = False
            else:
                print(f"  ✓ {inserted} pose priors inserted")
            
            # Step 3: 特徴点マッチング
            if not self.run_feature_matcher(database_path, progress_callback):
                return None, None
            
            # Step 4: pose_prior_mapperを実行
            if use_pose_priors:
                if not self.run_pose_prior_mapper(session_dir, colmap_dir, progress_callback):
                    print("Warning: pose_prior_mapper failed, trying standard mapper...")
                    if not self.run_mapper(session_dir, colmap_dir, progress_callback):
                        return None, None
            else:
                if not self.run_mapper(session_dir, colmap_dir, progress_callback):
                    return None, None
        
        else:
            # 通常のSfMモード（方式3）
            print("\n=== COLMAP SfM Mode (Standard) ===")
            print("  Running full SfM (Structure from Motion)")
            
            # Step 1: 特徴点抽出
            if not self.run_feature_extractor(session_dir, database_path, parser.intrinsics, progress_callback):
                return None, None
            
            # Step 2: 特徴点マッチング（config.yamlのmatcher設定に従う）
            if not self.run_feature_matcher(database_path, progress_callback):
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
        
        # 後処理1: COLMAP→ARCore座標変換（常に実行）
        colmap_config = self.config.get('colmap', {})
        
        if progress_callback:
            progress_callback(84, "Computing coordinate transform (COLMAP → ARCore)...")
        
        # COLMAP→ARCore座標変換を計算
        transform = self._compute_colmap_to_arcore_transform(parser, colmap_dir)
        
        # 変換をファイルに保存
        if transform is not None:
            transform_path = result_dir / "colmap_to_arcore_transform.json"
            import json
            transform_data = {
                'scale': float(transform['scale']),
                'rotation': transform['rotation'].tolist(),
                'colmap_centroid': transform['colmap_centroid'].tolist(),
                'arcore_centroid': transform['arcore_centroid'].tolist(),
                'mean_error': float(transform['mean_error']),
                'median_error': float(transform['median_error']),
            }
            with open(transform_path, 'w') as f:
                json.dump(transform_data, f, indent=2)
            print(f"  Transform saved: scale={transform['scale']:.4f}, mean_error={transform['mean_error']:.3f}m")
        
        if transform is not None:
            if progress_callback:
                progress_callback(85, "Transforming point cloud to ARCore coordinates...")
            
            points = np.asarray(pcd.points)
            colors = np.asarray(pcd.colors) if pcd.has_colors() else None
            normals = np.asarray(pcd.normals) if pcd.has_normals() else None
            
            # 点群をARCore座標系に変換
            points_arcore = self._transform_points_to_arcore(points, transform)
            
            # オプション: カメラからの距離でフィルタリング
            distance_filter = colmap_config.get('distance_filter', {})
            if distance_filter.get('enable', False):
                max_distance = distance_filter.get('max_distance', 3.0)
                min_distance = distance_filter.get('min_distance', 0.1)
                
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
                    filtered_colors = colors[mask] if colors is not None and len(colors) == len(points) else None
                    filtered_normals = normals[mask] if normals is not None and len(normals) == len(points) else None
                    
                    print(f"  Camera distance filter ({min_distance}-{max_distance}m): {len(points_arcore):,} → {len(filtered_points):,} points")
                    points_arcore = filtered_points
                    colors = filtered_colors
                    normals = filtered_normals
            
            # 変換済み点群を作成
            pcd_transformed = o3d.geometry.PointCloud()
            pcd_transformed.points = o3d.utility.Vector3dVector(points_arcore)
            
            if colors is not None and len(colors) == len(points_arcore):
                pcd_transformed.colors = o3d.utility.Vector3dVector(colors)
            if normals is not None and len(normals) == len(points_arcore):
                # 法線も変換（回転のみ）
                normals_transformed = normals @ transform['rotation']
                pcd_transformed.normals = o3d.utility.Vector3dVector(normals_transformed)
            
            print(f"  Coordinate system: ARCore (transformed)")
            pcd = pcd_transformed
        else:
            print("  Warning: Transform failed, using original COLMAP coordinates")
        
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
            
            # Step 12: ARCore軌跡を保存（点群と同じ座標系）
            self._save_trajectory(parser, result_dir)
            
            return pcd, mesh
            
        except Exception as e:
            print(f"Error generating mesh: {e}")
            import traceback
            traceback.print_exc()
            return pcd, None

