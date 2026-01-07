"""
Monocular Depth Estimation using MiDaS
RGB画像から深度を推定
"""

import numpy as np
from pathlib import Path
from typing import Optional, Callable
import cv2

# PyTorch
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("Warning: PyTorch not available, MiDaS depth estimation disabled")


class MiDaSDepthEstimator:
    """
    MiDaS/DPT による Monocular Depth Estimation
    
    RGB画像から深度マップを推定する。
    ARCore Depth APIが使えない場合の代替手段。
    """
    
    # 利用可能なモデル
    MODELS = {
        "DPT_Large": "DPT_Large",           # 最高精度、低速
        "DPT_Hybrid": "DPT_Hybrid",         # バランス
        "MiDaS_small": "MiDaS_small",       # 高速、低精度
        "DPT_BEiT_L_512": "DPT_BEiT_L_512", # 最新、高精度
    }
    
    def __init__(self, model_name: str = "DPT_Large", device: str = None, gpu_config: dict = None):
        """
        Args:
            model_name: 使用するモデル名
            device: "cuda" or "cpu" (Noneの場合は自動選択)
            gpu_config: GPU設定辞書（config.yamlのgpuセクション）
        """
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is required for MiDaS depth estimation")
        
        self.model_name = model_name
        self.gpu_config = gpu_config or {}
        
        # GPU設定からデバイスを決定
        if device:
            self.device = device
        elif self.gpu_config.get('enabled', True) and self.gpu_config.get('use_cuda', True):
            # GPUが有効でCUDAが利用可能な場合
            if torch.cuda.is_available():
                device_id = self.gpu_config.get('device_id', 0)
                self.device = f"cuda:{device_id}"
                # GPUメモリ設定
                if self.gpu_config.get('allow_growth', True):
                    # メモリを動的に確保（デフォルト動作）
                    pass
                else:
                    # メモリ使用率を制限
                    memory_fraction = self.gpu_config.get('memory_fraction', 0.9)
                    torch.cuda.set_per_process_memory_fraction(memory_fraction, device_id)
            else:
                # CUDAが利用できない場合
                if self.gpu_config.get('allow_fallback_to_cpu', False):
                    self.device = "cpu"
                    print("Warning: CUDA not available, falling back to CPU")
                else:
                    raise RuntimeError("CUDA is not available and fallback to CPU is disabled")
        else:
            # GPUが無効な場合
            self.device = "cpu"
        
        self.model = None
        self.transform = None
        self._initialized = False
    
    def initialize(self):
        """モデルを初期化（遅延ロード）"""
        if self._initialized:
            return
        
        print(f"Loading MiDaS model: {self.model_name} on {self.device}...")
        
        try:
            # torch.hubからMiDaSをロード
            self.model = torch.hub.load("intel-isl/MiDaS", self.model_name)
            self.model.to(self.device)
            self.model.eval()
            
            # 対応するトランスフォームをロード
            midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")
            
            if self.model_name in ["DPT_Large", "DPT_Hybrid", "DPT_BEiT_L_512"]:
                self.transform = midas_transforms.dpt_transform
            else:
                self.transform = midas_transforms.small_transform
            
            self._initialized = True
            print(f"MiDaS model loaded successfully")
            
        except Exception as e:
            print(f"Failed to load MiDaS model: {e}")
            raise
    
    def estimate_depth(self, 
                       image: np.ndarray,
                       normalize: bool = True) -> np.ndarray:
        """
        RGB画像から深度を推定
        
        Args:
            image: RGB画像 (H, W, 3) uint8
            normalize: 深度値を正規化するか
            
        Returns:
            深度マップ (H, W) float32
            - normalize=True: 0-1の範囲
            - normalize=False: 相対深度値
        """
        if not self._initialized:
            self.initialize()
        
        # BGR to RGB (OpenCVの場合)
        if image.shape[2] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else image
        else:
            img_rgb = image
        
        # 入力をトランスフォーム
        input_batch = self.transform(img_rgb).to(self.device)
        
        # 推論
        with torch.no_grad():
            prediction = self.model(input_batch)
            
            # 元のサイズにリサイズ
            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=image.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        
        depth = prediction.cpu().numpy()
        
        # 正規化（オプション）
        if normalize:
            depth_min = depth.min()
            depth_max = depth.max()
            if depth_max - depth_min > 0:
                depth = (depth - depth_min) / (depth_max - depth_min)
            else:
                depth = np.zeros_like(depth)
        
        return depth.astype(np.float32)
    
    def estimate_depth_metric(self,
                              image: np.ndarray,
                              scale: float = 1.0,
                              shift: float = 0.0) -> np.ndarray:
        """
        メートル単位の深度を推定（較正済みの場合）
        
        MiDaSは相対深度を出力するため、スケールとシフトで
        メートル単位に変換する必要がある。
        
        Args:
            image: RGB画像
            scale: 深度スケール係数
            shift: 深度シフト値
            
        Returns:
            深度マップ (m単位)
        """
        relative_depth = self.estimate_depth(image, normalize=False)
        
        # 相対深度を反転（MiDaSは近いほど大きい値を出力）
        relative_depth = 1.0 / (relative_depth + 1e-6)
        
        # スケール・シフト適用
        metric_depth = scale * relative_depth + shift
        
        # 有効範囲にクリップ (0.1m - 10m)
        metric_depth = np.clip(metric_depth, 0.1, 10.0)
        
        return metric_depth.astype(np.float32)
    
    def process_images(self,
                       image_paths: list,
                       output_dir: Path,
                       progress_callback: Callable[[int, str], None] = None) -> list:
        """
        複数画像の深度を推定して保存
        
        Args:
            image_paths: 入力画像パスのリスト
            output_dir: 出力ディレクトリ
            progress_callback: 進捗コールバック
            
        Returns:
            出力深度ファイルパスのリスト
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_paths = []
        total = len(image_paths)
        
        for i, img_path in enumerate(image_paths):
            img_path = Path(img_path)
            
            # 画像読み込み
            image = cv2.imread(str(img_path))
            if image is None:
                print(f"Failed to read image: {img_path}")
                continue
            
            # 深度推定
            depth = self.estimate_depth(image, normalize=True)
            
            # 16bit PNGとして保存 (0-65535にスケール)
            depth_16bit = (depth * 65535).astype(np.uint16)
            output_path = output_dir / f"depth_{img_path.stem}.png"
            cv2.imwrite(str(output_path), depth_16bit)
            
            output_paths.append(output_path)
            
            if progress_callback:
                progress = int((i + 1) / total * 100)
                progress_callback(progress, f"Estimated depth {i + 1}/{total}")
        
        return output_paths


def estimate_depth_for_session(session_dir: Path,
                               output_dir: Path = None,
                               model_name: str = "DPT_Large",
                               progress_callback: Callable[[int, str], None] = None,
                               gpu_config: dict = None,
                               device: str = None) -> bool:
    """
    セッション内の全画像の深度を推定
    
    Args:
        session_dir: セッションディレクトリ
        output_dir: 出力ディレクトリ（Noneの場合は session_dir/depth_estimated）
        model_name: MiDaSモデル名
        progress_callback: 進捗コールバック
        gpu_config: GPU設定辞書（config.yamlのgpuセクション）
        device: デバイス指定（"cuda" or "cpu"）
        
    Returns:
        成功したかどうか
    """
    session_dir = Path(session_dir)
    images_dir = session_dir / "images"
    
    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        return False
    
    # 出力ディレクトリ
    if output_dir is None:
        output_dir = session_dir / "depth_estimated"
    output_dir = Path(output_dir)
    
    # 画像リスト
    image_paths = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
    image_paths = sorted(image_paths)
    
    if not image_paths:
        print("No images found")
        return False
    
    print(f"Estimating depth for {len(image_paths)} images...")
    
    try:
        estimator = MiDaSDepthEstimator(
            model_name=model_name,
            device=device,
            gpu_config=gpu_config
        )
        estimator.process_images(image_paths, output_dir, progress_callback)
        return True
        
    except Exception as e:
        print(f"Depth estimation failed: {e}")
        return False


# テスト用
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python depth_estimation.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"Failed to read image: {image_path}")
        sys.exit(1)
    
    estimator = MiDaSDepthEstimator(model_name="MiDaS_small")  # 高速版
    depth = estimator.estimate_depth(image)
    
    # 可視化
    depth_vis = (depth * 255).astype(np.uint8)
    depth_colored = cv2.applyColorMap(depth_vis, cv2.COLORMAP_INFERNO)
    
    cv2.imshow("Depth", depth_colored)
    cv2.waitKey(0)

