# GPU対応版 ARCore + Open3D

このフォルダは、**すべてのOpen3D処理をGPU対応に再実装した**ARCore + Open3Dサーバーです。

## 🚀 主な特徴

- ✅ **GPU対応の深度推定**: MiDaS/PyTorch経由でGPUで実行
- ✅ **GPU対応の点群処理**: Open3D Tensor APIを使用
- ✅ **GPU対応のメッシュ生成**: 可能な範囲でGPU加速
- ✅ **自動フォールバック**: GPUが利用できない場合、自動的にCPU版に切り替え
- ⚠️ **TSDF統合**: 現在はCPUで実行（Tensor APIが完全サポートされ次第、GPU対応予定）

詳細は `GPU_IMPLEMENTATION.md` を参照してください。

## インストールとセットアップ

### 前提条件

このGPU対応版は、元の`arcore-open3d`フォルダの仮想環境を再利用します。

### 1. 元の仮想環境の確認

```bash
# 元の仮想環境が存在することを確認
ls /opt/arcore-open3d/venv/bin/python
```

### 2. CUDA対応のPyTorchをインストール（オプション）

元の仮想環境にCUDA対応のPyTorchをインストールする場合：

```bash
# 元の仮想環境をアクティベート
source /opt/arcore-open3d/venv/bin/activate

# CUDA 11.8版
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# または、CUDA 12.1版（最新）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 3. GPU設定の確認

`config.yaml`の`gpu`セクションでGPU設定を確認してください：

```yaml
gpu:
  enabled: true
  device_id: 0
  use_cuda: true
  cuda_available: true
  allow_fallback_to_cpu: false
  memory_fraction: 0.9
  allow_growth: true
```

## GPU設定の説明

- `enabled`: GPUを使用するかどうか
- `device_id`: 使用するGPUデバイスID（複数GPUがある場合）
- `use_cuda`: CUDAを使用するかどうか
- `cuda_available`: CUDAが利用可能かどうか（自動検出も可能）
- `allow_fallback_to_cpu`: GPUが利用できない場合にCPUにフォールバックするか
- `memory_fraction`: GPUメモリの使用率（0.0-1.0）
- `allow_growth`: メモリを必要に応じて動的に確保するか

## 使用方法

### 方法1: 起動スクリプトを使用（推奨）

```bash
./run.sh
```

このスクリプトは自動的に元の仮想環境をアクティベートしてからサーバーを起動します。

### 方法2: 手動で仮想環境をアクティベート

```bash
# 元の仮想環境をアクティベート
source /opt/arcore-open3d/venv/bin/activate

# サーバーを起動
cd /opt/arcore-open3d-gpu
python main.py
```

GPUが利用可能な場合、自動的にGPUが使用されます。

## トラブルシューティング

### CUDAが利用できない場合

1. CUDAがインストールされているか確認：
   ```bash
   nvidia-smi
   ```

2. PyTorchがCUDAを認識しているか確認：
   ```python
   import torch
   print(torch.cuda.is_available())
   ```

3. `config.yaml`で`allow_fallback_to_cpu: true`に設定すると、CPUにフォールバックします。

### GPUメモリ不足の場合

`config.yaml`で`memory_fraction`を小さくするか、`allow_growth: true`に設定してください。

