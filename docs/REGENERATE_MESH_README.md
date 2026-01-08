# メッシュ再生成スクリプト（GPU対応版）

## 概要

`regenerate_mesh.py`は、既存データのメッシュを再生成するGPU対応スクリプトです。

## 機能

1. **点群からメッシュを再生成** (`pointcloud`モード)
   - 点群ファイル（`point_cloud.ply`）からメッシュを生成
   - GPU対応版のMeshGeneratorを使用して高速処理

2. **既存メッシュの品質向上** (`existing`モード)
   - 既存のメッシュファイルに品質向上処理を適用
   - yaml設定に基づいた平滑化、クリーンアップ、簡略化

## GPU対応

- **自動GPU検出**: yaml設定の`gpu.enabled=true`でGPU加速が有効
- **自動フォールバック**: GPUが利用できない場合、自動的にCPU版に切り替え
- **GPU情報表示**: 使用するGPUデバイス情報を表示

## 使用方法

### 既存メッシュの品質向上

```bash
# 仮想環境をアクティベート
source /opt/arcore-open3d/venv/bin/activate

# 既存メッシュに品質向上処理を適用
python regenerate_mesh.py <job_id> existing

# 例
python regenerate_mesh.py 1611626e existing
```

### 点群からメッシュを再生成

```bash
# 点群からメッシュを再生成
python regenerate_mesh.py <job_id> pointcloud

# 例
python regenerate_mesh.py 1611626e pointcloud
```

## 適用される処理

### 1. メッシュのクリーンアップ
- 重複頂点・三角形の削除
- 非多様体エッジの削除
- 退化三角形の削除
- 未参照頂点の削除

### 2. メッシュの平滑化（yaml設定を適用）
- **方法**: `mesh.smoothing.method` (`laplacian` または `taubin`)
- **反復回数**: `mesh.smoothing.iterations` (デフォルト: 5)
- **ラムダ値**: `mesh.smoothing.lambda_filter` (デフォルト: 0.5)

### 3. 簡略化（必要に応じて）
- **最大三角形数**: `output.mesh.max_triangles_for_viewer` (デフォルト: 1000000)
- 簡略化後もクリーンアップを実行

### 4. ASCII形式で保存
- Three.jsのPLYLoaderと互換性がある形式
- 色情報も保持

## GPU設定

`config.yaml`でGPU設定を確認:

```yaml
gpu:
  enabled: true
  device_id: 0
  use_cuda: true
```

## 出力

処理が成功すると、以下の情報が表示されます:

```
✓ GPU available: NVIDIA GeForce GTX 1660 Ti (Device 0)
Reading point cloud from: /opt/arcore-open3d-gpu/data/results/1611626e/point_cloud.ply
Point cloud: 9370845 points
Generating mesh from point cloud (GPU accelerated)...
  Using GPU device: CUDA:0
Generated mesh: 11943991 vertices, 16907760 triangles
Cleaning up mesh...
Smoothing mesh (laplacian, 5 iterations, lambda=0.5)...
✓ Mesh smoothed
Simplifying mesh to 500000 triangles...
✓ Simplified: 499999 triangles (16907760 -> 499999)
✓ Mesh saved successfully
  Final: 1935562 vertices, 499999 triangles
```

## 注意事項

- 大きなメッシュの処理には時間がかかる場合があります
- GPUメモリが不足する場合は、`voxel_length`を大きくするか、`max_triangles_for_viewer`を小さくしてください
- 仮想環境（`/opt/arcore-open3d/venv`）をアクティベートしてから実行してください

