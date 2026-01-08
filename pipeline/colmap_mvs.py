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
        self.max_image_size = colmap_config.get('max_image_size', 3200)  # 画像の最大サイズ
        self.patch_match_iterations = colmap_config.get('patch_match_iterations', 5)  # Patch Matchの反復回数
        self.fusion_min_num_pixels = colmap_config.get('fusion_min_num_pixels', 5)  # 融合時の最小ピクセル数
        
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
        
        try:
            # CUDA対応版がインストールされているため、GPUオプションを有効化
            gpu_options = []
            if self.use_gpu:
                gpu_options = ["--PatchMatchStereo.gpu_index", "0"]
                print("  Using GPU for Patch Match Stereo (CUDA enabled)")
            else:
                print("  Using CPU for Patch Match Stereo (GPU disabled)")
            
            result = subprocess.run([
                self.colmap_path, "patch_match_stereo",
                "--workspace_path", str(workspace_path),
                "--workspace_format", "COLMAP",
                "--PatchMatchStereo.geom_consistency", "true",
                "--PatchMatchStereo.filter", "true",  # フィルタリングを有効化（必須）
                "--PatchMatchStereo.num_iterations", str(self.patch_match_iterations),
                *gpu_options
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
                "--input_type", "geometric",
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
        
        # Step 3: ARCore VIOのポーズからCOLMAPモデルを作成（初期値として使用）
        if not self.create_colmap_model_from_arcore_poses(parser, colmap_dir, progress_callback):
            return None, None
        
        # Step 4: Point Triangulator（ARCoreポーズを使用して特徴点を3D点に変換）
        # 注意: Rig IDエラーのため、point_triangulatorはスキップ
        # ARCoreポーズがあれば、image_undistorterとpatch_match_stereoは直接実行可能
        print("  Skipping point_triangulator (ARCore poses are sufficient)")
        
        # Step 5: Bundle Adjuster（ARCoreポーズを初期値として使用）
        # 注意: sparse reconstructionに点がない場合、bundle_adjusterは動作しない
        # ARCoreポーズを使用して続行
        print("  Skipping bundle_adjuster (no 3D points to adjust)")
        
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

