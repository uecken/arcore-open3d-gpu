# 現在のGPU使用状況まとめ

## 📊 実際にGPUが使われている処理

### ✅ GPUで実行されている処理

1. **深度推定（MiDaS/PyTorch）** ⚠️ **条件付きでGPU使用**
   - **ファイル**: `pipeline/depth_estimation.py`
   - **使用箇所**: `MiDaSDepthEstimator.estimate_depth()`
   - **デバイス**: `cuda:0` (PyTorch)
   - **条件**: **Depthデータがない場合のみ使用**
   - **現在の状況**: ログに "Has depth: True" とあるため、**使用されていない**

### ❌ GPU対応済みだが、実際にはCPUで実行されている処理

2. **TSDF Volume統合** - **CPUで実行**
   - **ファイル**: `pipeline/rgbd_integration_gpu.py`
   - **理由**: `ScalableTSDFVolume`はGPUデバイスパラメータをサポートしていない
   - **ログ**: "Note: ScalableTSDFVolume runs on CPU"
   - **実際の実行**: CPU
   - **影響**: メインの処理がCPUで実行されている

3. **点群処理** - **CPUで実行（フォールバック）**
   - **ファイル**: `pipeline/rgbd_integration_gpu.py`
   - **メソッド**: `_process_point_cloud_gpu()`
   - **状態**: Tensor APIを使用しようとするが、エラーでCPUにフォールバック
   - **実際の実行**: CPU

4. **メッシュ生成** - **CPUで実行（フォールバック）**
   - **ファイル**: `pipeline/mesh_generation_gpu.py`
   - **メソッド**: `_poisson_reconstruction_gpu()`
   - **状態**: Tensor APIを使用しようとするが、実際にはCPUで実行
   - **実際の実行**: CPU

## 🔍 現在のログから判断

```
[1611626e] Frames: 209, Has depth: True
✓ Open3D GPU device initialized: CUDA:0
ℹ Creating TSDF Volume (device: CUDA:0)
  Note: ScalableTSDFVolume runs on CPU.
Integrated 207/207 frames
```

**結論**: 
- ✅ Open3DのCUDAデバイスは初期化されている
- ❌ **実際の処理はCPUで実行されている**
- ❌ 深度データがあるため、MiDaS深度推定（GPU）は使用されていない
- ❌ **現在、GPUはほとんど使用されていない**

## 📈 GPU使用率の確認

```bash
# プロセスごとのGPU使用状況
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# 現在のサーバープロセスのGPU使用状況
ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}' | xargs -I {} sh -c 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv | grep "^{}," || echo "PID {} is not using GPU"'
```

## 💡 改善の方向性

### 即座に実装可能

1. **深度推定を強制的に使用**
   - Depthデータがあっても、MiDaSで再推定して品質向上
   - GPUを使用する機会を増やす

2. **点群・メッシュ処理のGPU化を確認**
   - Tensor APIのエラー原因を調査
   - フォールバックを減らす

### 中期的に実装

3. **Open3D Tensor APIの完全実装**
   - TSDF統合をGPUで実行
   - メモリ効率を保ちながらGPU加速

## 🎯 現状のまとめ

| 処理 | GPU対応 | 実際の実行 | GPU使用率 |
|------|---------|-----------|-----------|
| 深度推定（MiDaS） | ✅ | ❌（Depthデータがあるため未使用） | 0% |
| TSDF統合 | ⚠️ | ❌（CPU） | 0% |
| 点群処理 | ⚠️ | ❌（CPU） | 0% |
| メッシュ生成 | ⚠️ | ❌（CPU） | 0% |

**総合**: 現在、GPUは**ほとんど使用されていない**

