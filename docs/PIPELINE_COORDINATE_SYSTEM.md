# パイプライン座標系ガイド

## 概要

本システムはARCoreで取得したデータをCOLMAP MVSで処理し、3Dモデルを生成します。
ARCoreとCOLMAPは異なる座標系を使用するため、統一された座標系への変換が必要です。

## 座標系の統一方針

**最終座標系: ARCore座標系**

すべてのデータをARCore座標系に統一することで、RFIDタグの位置が正確に表示されます。

```
ARCore座標系:
  Y軸: 上方向（重力の逆方向）
  Z軸: 後方（カメラの背面方向）
  X軸: 右方向
  原点: セッション開始時のカメラ位置
  単位: メートル
```

## パイプラインの流れ

```
┌─────────────────────────────────────────────────────────────────┐
│                      入力データ（ARCore）                        │
├─────────────────────────────────────────────────────────────────┤
│  - images/: RGB画像                                              │
│  - depth/: 深度画像（ARCore Depth API）                          │
│  - ARCore_sensor_pose.txt: カメラポーズ（ARCore座標系）           │
│  - camera_intrinsics.json: カメラ内部パラメータ                  │
│  - rfid_detections.json: RFIDタグ検出位置（ARCore座標系）        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    COLMAP MVS パイプライン                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Feature Extraction: 特徴点抽出                              │
│  2. Exhaustive Matcher: 特徴点マッチング                        │
│  3. Mapper (SfM): 3D再構築 → COLMAP座標系で出力                 │
│  4. Image Undistorter: 歪み補正                                 │
│  5. Patch Match Stereo: 密な深度マップ生成                      │
│  6. Stereo Fusion: 点群生成（COLMAP座標系）                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    座標変換（COLMAP → ARCore）                   │
├─────────────────────────────────────────────────────────────────┤
│  Procrustes分析による変換パラメータ計算:                         │
│                                                                 │
│  1. ARCoreカメラ位置を取得（parser.frames）                      │
│  2. COLMAPカメラ位置を取得（images.bin）                         │
│  3. 共通画像でProcrustes分析                                     │
│     - スケール: ARCore_scale / COLMAP_scale                     │
│     - 回転行列: orthogonal_procrustes()                         │
│     - 並進: 重心の差分                                           │
│                                                                 │
│  変換式:                                                         │
│  p_arcore = scale × R × (p_colmap - colmap_centroid)            │
│             + arcore_centroid                                    │
│                                                                 │
│  典型的なスケール: 約0.4（COLMAPは約2.4倍大きい）                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    距離フィルタリング                            │
├─────────────────────────────────────────────────────────────────┤
│  カメラからの距離でフィルタリング（config.yaml設定）:            │
│                                                                 │
│  colmap:                                                        │
│    distance_filter:                                             │
│      enable: true                                               │
│      min_distance: 0.1  # 最小距離（m）                         │
│      max_distance: 3.0  # 最大距離（m）                         │
│                                                                 │
│  アルゴリズム:                                                   │
│  1. 変換済み点群の各点に対して                                   │
│  2. 最近傍のARCoreカメラ位置を検索（KD-Tree）                    │
│  3. 距離がmin〜max範囲内の点のみ保持                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      後処理                                      │
├─────────────────────────────────────────────────────────────────┤
│  1. 統計的外れ値除去（Statistical Outlier Removal）              │
│  2. Poisson Surface Reconstruction（メッシュ生成）              │
│  3. Laplacianスムージング                                        │
│  4. 小さな連結成分の除去                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      出力データ                                  │
├─────────────────────────────────────────────────────────────────┤
│  すべてARCore座標系:                                             │
│  - point_cloud.ply: 点群                                        │
│  - mesh.ply: メッシュ                                           │
│  - trajectory.json: カメラ軌跡                                  │
│  - rfid_positions.json: RFIDタグ位置（コピー）                  │
└─────────────────────────────────────────────────────────────────┘
```

## Viewer表示時の座標処理

```
┌─────────────────────────────────────────────────────────────────┐
│                    Viewer座標処理                                │
├─────────────────────────────────────────────────────────────────┤
│  1. メッシュ読み込み時:                                          │
│     - Bounding Boxの中心を計算                                   │
│     - 中心オフセット（sceneCenterOffset）を保存                  │
│     - メッシュを中心化（グリッド原点に移動）                     │
│                                                                 │
│  2. 軌跡読み込み時:                                              │
│     - 同じsceneCenterOffsetを適用                                │
│     - メッシュと同じ位置に表示                                   │
│                                                                 │
│  3. RFID読み込み時:                                              │
│     - 同じsceneCenterOffsetを適用                                │
│     - メッシュと同じ位置に表示                                   │
│                                                                 │
│  結果: すべてのデータがグリッド中心に統一表示                    │
└─────────────────────────────────────────────────────────────────┘
```

## trajectory.json フォーマット

```json
{
  "poses": [
    {
      "position": {
        "x": 0.220463,
        "y": 0.077463,
        "z": 0.098415
      },
      "timestamp": null
    },
    ...
  ],
  "count": 209,
  "coordinate_system": "arcore"
}
```

## 設定ファイル（config.yaml）

```yaml
# 処理モード
default_mode: "mvs"  # "rgbd" または "mvs"

# COLMAP設定
colmap:
  path: "colmap"
  max_image_size: 1600
  patch_match_iterations: 3
  fusion_min_num_pixels: 5
  window_radius: 5
  cache_size: 16
  
  # 距離フィルタ（カメラからの距離）
  distance_filter:
    enable: true
    min_distance: 0.1
    max_distance: 3.0

# メッシュ設定
mesh:
  poisson:
    depth: 10
    density_threshold_percentile: 5
  smoothing:
    enable: true
    iterations: 10
    lambda_filter: 0.5

# GPU設定
gpu:
  enabled: true
  use_cuda: true
```

## 主要コンポーネント

### 1. COLMAPMVSPipeline (`pipeline/colmap_mvs.py`)

```python
class COLMAPMVSPipeline:
    def process_session(parser, session_dir, result_dir, progress_callback):
        # COLMAP処理 → 座標変換 → フィルタリング → メッシュ生成
        
    def _compute_colmap_to_arcore_transform(parser, colmap_dir):
        # Procrustes分析で変換パラメータ計算
        
    def _transform_points_to_arcore(points, transform):
        # COLMAP座標 → ARCore座標変換
        
    def _get_camera_positions(parser):
        # ARCoreカメラ位置取得
        
    def _save_trajectory(parser, result_dir):
        # 軌跡保存（ARCore座標系）
```

### 2. Viewer (`static/viewer.html`)

```javascript
// 状態変数
let sceneCenterOffset = new THREE.Vector3(0, 0, 0);

// メッシュ読み込み
async function loadMesh(jobId) {
    // 中心オフセットを保存
    sceneCenterOffset.copy(center);
    geometry.translate(-center.x, -center.y, -center.z);
}

// 軌跡読み込み
async function loadTrajectory(jobId) {
    // 同じオフセットを適用
    positions.push(
        pos.x - sceneCenterOffset.x,
        pos.y - sceneCenterOffset.y,
        pos.z - sceneCenterOffset.z
    );
}
```

## トラブルシューティング

### 軌跡とメッシュがずれる場合

1. **座標系の不一致**: `trajectory.json` の `coordinate_system` が `"arcore"` であることを確認
2. **中心オフセット**: Viewerで `sceneCenterOffset` が正しく適用されているか確認
3. **再生成**: セッションを再処理して新しい `trajectory.json` を生成

### RFIDタグの位置がずれる場合

1. RFIDデータはARCore座標系で記録されている必要がある
2. `rfid_positions.json` の位置がARCore座標系であることを確認
3. Viewerで同じ `sceneCenterOffset` が適用されているか確認

### スケールが合わない場合

1. Procrustes分析のスケール値を確認（通常0.3〜0.5）
2. 共通画像数が十分（10枚以上）あることを確認
3. ARCoreポーズの品質を確認

## 参考情報

- ARCore座標系: https://developers.google.com/ar/reference/java/arcore/reference/com/google/ar/core/Frame
- COLMAP: https://colmap.github.io/
- Procrustes分析: https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.orthogonal_procrustes.html

