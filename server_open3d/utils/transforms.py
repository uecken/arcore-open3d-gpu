"""
座標変換ユーティリティ
"""

import numpy as np
from typing import Tuple


def quaternion_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """
    クォータニオンから3x3回転行列に変換
    
    Args:
        q: [qw, qx, qy, qz] 形式のクォータニオン
        
    Returns:
        3x3回転行列
    """
    qw, qx, qy, qz = q
    
    # 正規化
    norm = np.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
    if norm > 0:
        qw, qx, qy, qz = qw/norm, qx/norm, qy/norm, qz/norm
    
    R = np.array([
        [1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw)],
        [2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw)],
        [2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy)]
    ])
    
    return R


def rotation_matrix_to_quaternion(R: np.ndarray) -> np.ndarray:
    """
    3x3回転行列からクォータニオンに変換
    
    Args:
        R: 3x3回転行列
        
    Returns:
        [qw, qx, qy, qz] 形式のクォータニオン
    """
    trace = np.trace(R)
    
    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        qw = 0.25 / s
        qx = (R[2, 1] - R[1, 2]) * s
        qy = (R[0, 2] - R[2, 0]) * s
        qz = (R[1, 0] - R[0, 1]) * s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        qw = (R[2, 1] - R[1, 2]) / s
        qx = 0.25 * s
        qy = (R[0, 1] + R[1, 0]) / s
        qz = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        qw = (R[0, 2] - R[2, 0]) / s
        qx = (R[0, 1] + R[1, 0]) / s
        qy = 0.25 * s
        qz = (R[1, 2] + R[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        qw = (R[1, 0] - R[0, 1]) / s
        qx = (R[0, 2] + R[2, 0]) / s
        qy = (R[1, 2] + R[2, 1]) / s
        qz = 0.25 * s
    
    return np.array([qw, qx, qy, qz])


def arcore_pose_to_matrix(qx: float, qy: float, qz: float, qw: float,
                          tx: float, ty: float, tz: float) -> np.ndarray:
    """
    ARCoreポーズを4x4変換行列に変換
    
    Args:
        qx, qy, qz, qw: クォータニオン成分
        tx, ty, tz: 平行移動成分
        
    Returns:
        4x4変換行列
    """
    q = np.array([qw, qx, qy, qz])
    R = quaternion_to_rotation_matrix(q)
    
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [tx, ty, tz]
    
    return T


def matrix_to_pose(T: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    4x4変換行列からクォータニオンと平行移動を抽出
    
    Args:
        T: 4x4変換行列
        
    Returns:
        (quaternion [qw, qx, qy, qz], translation [tx, ty, tz])
    """
    R = T[:3, :3]
    t = T[:3, 3]
    q = rotation_matrix_to_quaternion(R)
    return q, t


def transform_point_cloud(points: np.ndarray, T: np.ndarray) -> np.ndarray:
    """
    点群を変換行列で変換
    
    Args:
        points: Nx3の点群
        T: 4x4変換行列
        
    Returns:
        変換後の点群 Nx3
    """
    N = points.shape[0]
    ones = np.ones((N, 1))
    points_h = np.hstack([points, ones])  # Nx4
    transformed = (T @ points_h.T).T  # Nx4
    return transformed[:, :3]


def create_intrinsic_matrix(fx: float, fy: float, cx: float, cy: float) -> np.ndarray:
    """
    カメラ内部パラメータ行列を作成
    
    Args:
        fx, fy: 焦点距離
        cx, cy: 主点
        
    Returns:
        3x3内部パラメータ行列
    """
    K = np.array([
        [fx, 0, cx],
        [0, fy, cy],
        [0, 0, 1]
    ])
    return K


def arcore_to_open3d_pose(arcore_pose: np.ndarray) -> np.ndarray:
    """
    ARCore座標系からOpen3D座標系への変換
    
    ARCore: Y-up, -Z forward
    Open3D: Y-down, Z forward (一般的なCV座標系)
    
    Args:
        arcore_pose: ARCoreの4x4ポーズ行列
        
    Returns:
        Open3D用の4x4ポーズ行列
    """
    # Y軸とZ軸を反転する変換
    flip = np.array([
        [1, 0, 0, 0],
        [0, -1, 0, 0],
        [0, 0, -1, 0],
        [0, 0, 0, 1]
    ])
    
    return flip @ arcore_pose @ flip

