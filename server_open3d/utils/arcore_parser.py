"""
ARCore Data Parser
ARCoreアプリから送信されたデータを解析
"""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re


@dataclass
class CameraIntrinsics:
    """カメラ内部パラメータ"""
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    distortion: List[float] = field(default_factory=lambda: [0, 0, 0, 0, 0])
    
    @classmethod
    def from_json(cls, path: Path) -> 'CameraIntrinsics':
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(
            fx=data['fx'],
            fy=data['fy'],
            cx=data['cx'],
            cy=data['cy'],
            width=data['width'],
            height=data['height'],
            distortion=data.get('distortion', [0, 0, 0, 0, 0])
        )


@dataclass
class CameraPose:
    """カメラポーズ（位置・姿勢）"""
    timestamp: int  # nanoseconds
    qx: float
    qy: float
    qz: float
    qw: float
    tx: float
    ty: float
    tz: float
    
    @property
    def quaternion(self) -> np.ndarray:
        return np.array([self.qw, self.qx, self.qy, self.qz])
    
    @property
    def translation(self) -> np.ndarray:
        return np.array([self.tx, self.ty, self.tz])
    
    def to_matrix(self) -> np.ndarray:
        """4x4変換行列に変換"""
        from .transforms import quaternion_to_rotation_matrix
        
        R = quaternion_to_rotation_matrix(self.quaternion)
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = self.translation
        return T


@dataclass
class Frame:
    """フレームデータ"""
    timestamp: int
    image_path: Path
    depth_path: Optional[Path] = None
    pose: Optional[CameraPose] = None


@dataclass
class RFIDDetection:
    """RFID検出データ"""
    tag_id: str
    timestamp: int
    rssi: int
    pose: Optional[CameraPose] = None


class ARCoreDataParser:
    """ARCoreセッションデータのパーサー"""
    
    def __init__(self, session_dir: Path):
        self.session_dir = Path(session_dir)
        self.images_dir = self.session_dir / "images"
        self.depth_dir = self.session_dir / "depth"
        
        self.intrinsics: Optional[CameraIntrinsics] = None
        self.poses: Dict[int, CameraPose] = {}
        self.frames: List[Frame] = []
        self.rfid_detections: List[RFIDDetection] = []
        self.metadata: Dict[str, Any] = {}
    
    def parse(self) -> bool:
        """全データを解析"""
        try:
            self._parse_intrinsics()
            self._parse_poses()
            self._parse_images()
            self._parse_rfid()
            self._parse_metadata()
            return True
        except Exception as e:
            print(f"Parse error: {e}")
            return False
    
    def _parse_intrinsics(self):
        """カメラ内部パラメータを解析"""
        intrinsics_path = self.session_dir / "camera_intrinsics.json"
        if intrinsics_path.exists():
            self.intrinsics = CameraIntrinsics.from_json(intrinsics_path)
    
    def _parse_poses(self):
        """ポーズデータを解析"""
        poses_path = self.session_dir / "ARCore_sensor_pose.txt"
        if not poses_path.exists():
            return
        
        with open(poses_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        timestamp = int(parts[0])
                        pose = CameraPose(
                            timestamp=timestamp,
                            qx=float(parts[1]),
                            qy=float(parts[2]),
                            qz=float(parts[3]),
                            qw=float(parts[4]),
                            tx=float(parts[5]),
                            ty=float(parts[6]),
                            tz=float(parts[7])
                        )
                        self.poses[timestamp] = pose
                    except ValueError:
                        continue
    
    def _parse_images(self):
        """画像ファイルを解析してフレームを作成"""
        if not self.images_dir.exists():
            return
        
        for img_path in sorted(self.images_dir.glob("*.jpg")):
            # タイムスタンプを抽出 (frame_12345.jpg → 12345)
            match = re.search(r'frame_(\d+)', img_path.stem)
            if match:
                timestamp = int(match.group(1))
            else:
                timestamp = 0
            
            # 対応するDepthファイルを探す（.rawと.pngの両方をチェック）
            depth_path = None
            if self.depth_dir.exists():
                # まず.rawファイルを探す（ARCoreの生データ）
                depth_file_raw = self.depth_dir / f"depth_{timestamp}.raw"
                if depth_file_raw.exists():
                    depth_path = depth_file_raw
                else:
                    # .rawがない場合は.pngを探す
                    depth_file_png = self.depth_dir / f"depth_{timestamp}.png"
                    if depth_file_png.exists():
                        depth_path = depth_file_png
            
            # 最も近いポーズを見つける
            pose = self._find_nearest_pose(timestamp)
            
            frame = Frame(
                timestamp=timestamp,
                image_path=img_path,
                depth_path=depth_path,
                pose=pose
            )
            self.frames.append(frame)
    
    def _find_nearest_pose(self, timestamp: int) -> Optional[CameraPose]:
        """最も近いタイムスタンプのポーズを見つける"""
        if not self.poses:
            return None
        
        # 完全一致
        if timestamp in self.poses:
            return self.poses[timestamp]
        
        # 最も近いものを探す
        min_diff = float('inf')
        nearest_pose = None
        
        for ts, pose in self.poses.items():
            diff = abs(ts - timestamp)
            if diff < min_diff:
                min_diff = diff
                nearest_pose = pose
        
        return nearest_pose
    
    def _parse_rfid(self):
        """RFID検出データを解析"""
        rfid_path = self.session_dir / "rfid_detections.json"
        if not rfid_path.exists():
            return
        
        with open(rfid_path, 'r') as f:
            data = json.load(f)
        
        detections = data.get('detections', [])
        for d in detections:
            timestamp = d.get('timestamp', 0)
            pose_data = d.get('pose', {})
            
            pose = None
            if pose_data:
                pose = CameraPose(
                    timestamp=timestamp,
                    qx=pose_data.get('qx', 0),
                    qy=pose_data.get('qy', 0),
                    qz=pose_data.get('qz', 0),
                    qw=pose_data.get('qw', 1),
                    tx=pose_data.get('position', {}).get('x', 0),
                    ty=pose_data.get('position', {}).get('y', 0),
                    tz=pose_data.get('position', {}).get('z', 0)
                )
            
            detection = RFIDDetection(
                tag_id=d.get('tag_id', ''),
                timestamp=timestamp,
                rssi=d.get('rssi', 0),
                pose=pose
            )
            self.rfid_detections.append(detection)
    
    def _parse_metadata(self):
        """メタデータを解析"""
        metadata_path = self.session_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
    
    def get_frames_with_pose(self) -> List[Frame]:
        """ポーズが存在するフレームのみ取得"""
        return [f for f in self.frames if f.pose is not None]
    
    def get_frames_with_depth(self) -> List[Frame]:
        """Depthが存在するフレームのみ取得"""
        return [f for f in self.frames if f.depth_path is not None]
    
    def has_depth_data(self) -> bool:
        """Depthデータが存在するか"""
        return any(f.depth_path is not None for f in self.frames)
    
    def get_unique_rfid_tags(self) -> List[str]:
        """ユニークなRFIDタグIDのリスト"""
        return list(set(d.tag_id for d in self.rfid_detections))

