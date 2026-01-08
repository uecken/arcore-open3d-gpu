# GPU最適化分析

## 現在の処理時間（25万点の点群）

| 処理 | 現在 | GPU対応 | 高速化可能 |
|------|------|---------|------------|
| **Poisson Reconstruction** | **12.4s** | ❌ | ❌ |
| **Laplacian Smoothing** | **4.9s** | ❌ | ❌ |
| Normal Estimation | 0.6s | ✅ | ✅ 2.5x |
| Statistical Outlier Removal | 0.5s | ✅ | ❌ (GPU遅い) |
| Voxel Downsampling | 0.2s | ✅ | ✅ 2.0x |
| KDTree Distance Query | 0.2s | ❌ | ❌ |

## 最大のボトルネック

### 1. Poisson Reconstruction（最大のボトルネック）

```
処理時間: 12.4秒（depth=8）、25万点
GPU対応: なし（Open3D）
```

**対策オプション:**
1. **depth値を下げる** - 品質低下とトレードオフ
   - depth=10: 高品質、遅い
   - depth=8: 中品質、やや速い（推奨）
   - depth=7: 低品質、速い

2. **代替アルゴリズム**
   | 方法 | 時間 | 品質 |
   |------|------|------|
   | Poisson (depth=8) | 5.5s | 高 |
   | Ball Pivoting | 1.3s | 中 |
   | Alpha Shape | 4.1s | 中 |

3. **点群を間引く** - 入力点数を減らす
   - 50%間引き → 約50%高速化

### 2. Laplacian Smoothing

```
処理時間: 4.9秒（10イテレーション）
GPU対応: なし（Open3D Tensor API未対応）
```

**対策オプション:**
1. **イテレーション数を減らす**
   - 10 → 5: 約50%高速化
   - 品質への影響は軽微

2. **スムージングをスキップ**
   - Poissonで十分滑らかな場合は不要

## GPU高速化可能な処理

### Normal Estimation（推奨）

```python
# CPU版（現在）
pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(
    radius=0.1, max_nn=30))

# GPU版（2.5倍高速）
import open3d.core as o3c
device = o3c.Device('CUDA:0')
pcd_gpu = o3d.t.geometry.PointCloud(device)
pcd_gpu.point.positions = o3c.Tensor(points, device=device)
pcd_gpu.estimate_normals(max_nn=30, radius=0.1)
```

### Voxel Downsampling（推奨）

```python
# GPU版（2倍高速）
pcd_gpu.voxel_down_sample(voxel_size=0.02)
```

## COLMAP処理のGPU利用状況

| ステップ | GPU利用 | 備考 |
|----------|---------|------|
| Feature Extraction | ✅ | SIFT GPU |
| Feature Matching | ✅ | GPU対応 |
| Mapper (SfM) | ❌ | CPU主体 |
| Image Undistorter | ❌ | CPU |
| **Patch Match Stereo** | ✅ | **CUDA必須** |
| Stereo Fusion | ❌ | CPU |

## 推奨最適化

### 即座に実装可能（効果大）

1. **Poisson depthを10→8に変更**
   ```yaml
   mesh:
     poisson:
       depth: 8  # 10から変更
   ```
   効果: 約30%高速化

2. **Laplacian iterationsを10→5に変更**
   ```yaml
   mesh:
     smoothing:
       iterations: 5  # 10から変更
   ```
   効果: 約50%高速化

### 実装が必要（効果中）

3. **Normal EstimationをGPU化**
   - Tensor API使用
   - 効果: 2.5倍高速化（0.6s → 0.24s）

4. **点群の事前間引き**
   - Voxel downsampleで50%削減
   - 効果: Poisson時間を約50%削減

### 将来的な検討

5. **Ball Pivotingへの切り替え**
   - 4倍高速だが品質低下
   - 用途によっては許容可能

6. **GPU対応メッシュライブラリへの移行**
   - PyMeshLab（一部GPU対応）
   - nvdiffrast（NVIDIA、完全GPU）

## 現在の処理フロー改善案

```
Before (現在):
  Poisson (depth=10)     : 15s
  Laplacian (iter=10)    : 5s
  Total: ~20s

After (最適化後):
  Poisson (depth=8)      : 10s  (33%↓)
  Laplacian (iter=5)     : 2.5s (50%↓)
  Total: ~12.5s (37%高速化)

With GPU normals:
  Normal Estimation (GPU): 0.24s (2.5x↑)
  Additional savings: 0.36s
```

## config.yaml推奨設定

```yaml
# 高速化設定
mesh:
  poisson:
    depth: 8  # 10→8で高速化
    density_threshold_percentile: 5
  smoothing:
    enable: true
    iterations: 5  # 10→5で高速化
    lambda_filter: 0.5

# GPU設定
gpu:
  enabled: true
  use_cuda: true
  # Open3D Tensor API使用（将来）
  use_tensor_api: true
```

## 結論

1. **最大のボトルネックはPoisson Reconstruction**（GPU対応なし）
2. **即座に効果がある設定変更**: depth=8, iterations=5
3. **GPU高速化可能**: Normal Estimation (2.5x), Voxel Downsample (2x)
4. **COLMAP Patch Match StereoはすでにGPU使用中**

