# ARCore + Open3D 3D再構成サーバー

## 概要

ARCoreから取得したカメラポーズと画像データを使用し、Open3Dで3D再構成を行うサーバー。
COLMAPを使用せず、ARCoreのVIO（Visual-Inertial Odometry）ポーズを直接利用することで、
高速かつ効率的な3D再構成を実現する。

## アーキテクチャ比較

### 従来 (COLMAP)
```
画像 → COLMAP SfM → カメラポーズ推定 → Dense MVS → 点群/メッシュ
         ↑
    時間がかかる（SfMが重い）
```

### 新方式 (ARCore + Open3D)
```
ARCore → カメラポーズ (既知) + 画像 → Open3D → 点群/メッシュ
              ↑
         高速（SfM不要）
```

## メリット・デメリット

| 項目 | COLMAP方式 | Open3D方式 |
|------|-----------|-----------|
| カメラポーズ | SfMで推定 | ARCoreから直接取得 |
| 処理速度 | 遅い | **高速** |
| 精度 | 高い（最適化済み） | ARCore VIO精度に依存 |
| Depth情報 | 画像から推定 | ARCore Depth APIを活用可能 |
| 必要VRAM | 多い | **少ない** |
| セットアップ | 複雑 | **シンプル** |

## 処理パイプライン

### 1. 入力データ

ARCoreアプリから送信されるデータ:

```
session/
├── images/
│   ├── frame_12345.jpg
│   ├── frame_12346.jpg
│   └── ...
├── ARCore_sensor_pose.txt      # カメラポーズ（タイムスタンプ, qx,qy,qz,qw, tx,ty,tz）
├── camera_intrinsics.json      # fx, fy, cx, cy, width, height
├── depth/                      # (オプション) ARCore Depth
│   ├── depth_12345.png
│   └── ...
├── rfid_detections.json        # RFIDタグ検出データ
└── metadata.json
```

### 2. 処理モード

#### Mode A: Multi-View Stereo (MVS) - Depthなし
```python
# 画像ペアからdepthを推定
for i in range(len(images) - 1):
    depth = estimate_depth_from_stereo(images[i], images[i+1], poses[i], poses[i+1])
    integrate_rgbd(color=images[i], depth=depth, pose=poses[i])
```

#### Mode B: RGB-D Integration - Depthあり（推奨）
```python
# ARCore Depthを直接使用
for color, depth, pose in zip(images, depths, poses):
    rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(color, depth)
    volume.integrate(rgbd, intrinsic, pose)
```

#### Mode C: Point Cloud Fusion
```python
# ARCore点群を直接融合
combined_pcd = o3d.geometry.PointCloud()
for pcd, pose in zip(point_clouds, poses):
    pcd.transform(pose)
    combined_pcd += pcd
combined_pcd = combined_pcd.voxel_down_sample(voxel_size=0.01)
```

### 3. 出力

```
results/{job_id}/
├── point_cloud.ply         # 統合点群
├── mesh.ply               # メッシュ（Poisson/Ball Pivoting）
├── mesh_textured.obj      # テクスチャ付きメッシュ
├── rfid_positions.json    # RFID位置（3D座標）
└── metadata.json          # 処理結果メタデータ
```

## 技術仕様

### Open3D 処理フロー

```python
import open3d as o3d
import numpy as np

# 1. カメラ内部パラメータ設定
intrinsic = o3d.camera.PinholeCameraIntrinsic(
    width, height, fx, fy, cx, cy
)

# 2. TSDF Volume Integration
volume = o3d.pipelines.integration.ScalableTSDFVolume(
    voxel_length=0.005,           # 5mm解像度
    sdf_trunc=0.04,               # 4cmトランケーション
    color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
)

# 3. RGB-D画像を統合
for frame in frames:
    color = o3d.io.read_image(frame.color_path)
    depth = o3d.io.read_image(frame.depth_path)
    rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
        color, depth,
        depth_scale=1000.0,       # mm → m
        depth_trunc=3.0,          # 3m以上は無視
        convert_rgb_to_intensity=False
    )
    
    # ARCoreポーズを4x4行列に変換
    pose = arcore_pose_to_matrix(frame.pose)
    
    volume.integrate(rgbd, intrinsic, np.linalg.inv(pose))

# 4. メッシュ抽出
mesh = volume.extract_triangle_mesh()
mesh.compute_vertex_normals()

# 5. 点群抽出
pcd = volume.extract_point_cloud()
```

### Depthなしの場合（Monocular Depth Estimation）

```python
# MiDaS/DPTなどの深度推定モデルを使用
import torch
model = torch.hub.load("intel-isl/MiDaS", "DPT_Large")

def estimate_depth(image):
    input_batch = transform(image).unsqueeze(0)
    with torch.no_grad():
        prediction = model(input_batch)
    return prediction.squeeze().numpy()
```

### メッシュ生成オプション

| 手法 | 特徴 | 用途 |
|------|------|------|
| **TSDF + Marching Cubes** | 高品質、穴が少ない | 室内スキャン |
| **Poisson Surface** | 滑らか | 物体スキャン |
| **Ball Pivoting** | 高速、薄い構造に強い | 部分スキャン |
| **Alpha Shape** | パラメータ調整必要 | 点群境界 |

## API仕様

### エンドポイント

```
POST /api/v1/sessions/upload
  - 画像・ポーズ・深度データをアップロード
  - mode: "rgbd" | "mvs" | "pointcloud"

GET /api/v1/jobs/{job_id}/status
  - 処理ステータス

GET /scenes/{job_id}/point_cloud.ply
GET /scenes/{job_id}/mesh.ply
GET /scenes/{job_id}/mesh_textured.obj
```

### 設定

```yaml
# config.yaml
processing:
  mode: "rgbd"                    # rgbd / mvs / pointcloud
  voxel_size: 0.005               # 5mm
  depth_scale: 1000.0             # mm → m
  depth_trunc: 3.0                # 最大深度 3m
  
mesh:
  method: "poisson"               # poisson / ball_pivoting / alpha
  poisson_depth: 9                # Poisson再構成の深さ
  
optimization:
  enable_icp: true                # ICPによるポーズ補正
  icp_threshold: 0.02             # 2cm
```

## Android側の変更

### 必要な追加データ

1. **ARCore Depth（推奨）**
   - `frame.acquireDepthImage16Bits()` でDepthを取得
   - PNG (16bit) で保存

2. **ARCore Point Cloud**
   - `frame.acquirePointCloud()` で点群取得
   - PLY形式で保存（オプション）

### データ送信フォーマット

```java
// 深度画像の取得と保存
try (Image depthImage = frame.acquireDepthImage16Bits()) {
    saveDepthImage(depthImage, "depth_" + timestamp + ".png");
}
```

## 依存関係

```
# requirements.txt
open3d>=0.18.0
numpy>=1.26.0
torch>=2.1.0              # MiDaS用（オプション）
torchvision>=0.16.0
fastapi>=0.109.0
uvicorn>=0.27.0
pillow>=10.2.0
scipy>=1.12.0
```

## ディレクトリ構成

```
server_open3d/
├── README.md               # この仕様書
├── requirements.txt
├── main.py                 # FastAPIサーバー
├── pipeline/
│   ├── __init__.py
│   ├── rgbd_integration.py # RGB-D統合
│   ├── mvs_stereo.py       # MVSステレオ
│   ├── pointcloud_fusion.py # 点群融合
│   ├── mesh_generation.py  # メッシュ生成
│   └── depth_estimation.py # 深度推定（MiDaS）
├── utils/
│   ├── __init__.py
│   ├── arcore_parser.py    # ARCoreデータパーサー
│   └── transforms.py       # 座標変換
├── config.yaml             # 設定ファイル
└── viewer/
    └── index.html          # 3Dビューア
```

## 開発ロードマップ

### Phase 1: 基本機能
- [ ] ARCoreポーズパーサー
- [ ] RGB-D Integration (TSDF)
- [ ] 基本的なメッシュ生成

### Phase 2: Depth推定
- [ ] MiDaS/DPT統合
- [ ] Monocular depth → RGBD変換

### Phase 3: 最適化
- [ ] ICP ポーズ補正
- [ ] Loop closure検出
- [ ] 点群フィルタリング

### Phase 4: 品質向上
- [ ] テクスチャマッピング
- [ ] メッシュ最適化
- [ ] Gaussian Splatting統合

## パフォーマンス目標

| 処理 | 目標時間 | COLMAP比較 |
|------|---------|-----------|
| 50枚画像 処理 | < 30秒 | 5-10分 |
| メッシュ生成 | < 10秒 | 1-5分 |
| 合計 | < 1分 | 10-20分 |

## 参考リンク

- [Open3D Documentation](http://www.open3d.org/docs/)
- [ARCore Depth API](https://developers.google.com/ar/develop/depth)
- [MiDaS Depth Estimation](https://github.com/isl-org/MiDaS)
- [TSDF Volume Integration](http://www.open3d.org/docs/release/tutorial/pipelines/rgbd_integration.html)

