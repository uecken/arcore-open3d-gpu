# 現在のGPU使用状況

## 実際にGPUが使われている処理

### ✅ GPUで実行されている処理

1. **深度推定（MiDaS/PyTorch）** - **実際にGPU使用**
   - ファイル: `pipeline/depth_estimation.py`
   - 使用箇所: `MiDaSDepthEstimator.estimate_depth()`
   - デバイス: `cuda:0` (PyTorch)
   - 条件: Depthデータがない場合のみ使用（現在のログでは使用されていない）

### ⚠️ GPU対応済みだが、実際にはCPUで実行されている処理

2. **TSDF Volume統合** - **CPUで実行**
   - ファイル: `pipeline/rgbd_integration_gpu.py`
   - 理由: `ScalableTSDFVolume`はGPUデバイスパラメータをサポートしていない
   - ログ: "Note: ScalableTSDFVolume runs on CPU"
   - 実際の実行: CPU

3. **点群処理** - **部分的にGPU対応（主にCPU）**
   - ファイル: `pipeline/rgbd_integration_gpu.py`
   - メソッド: `_process_point_cloud_gpu()`
   - 状態: Tensor APIを使用しようとするが、フォールバックでCPU実行が多い

4. **メッシュ生成** - **部分的にGPU対応（主にCPU）**
   - ファイル: `pipeline/mesh_generation_gpu.py`
   - メソッド: `_poisson_reconstruction_gpu()`
   - 状態: Tensor APIを使用しようとするが、実際にはCPUで実行

## 現在のログから判断

```
[1611626e] Frames: 209, Has depth: True
✓ Open3D GPU device initialized: CUDA:0
ℹ Creating TSDF Volume (device: CUDA:0)
  Note: ScalableTSDFVolume runs on CPU.
Integrated 207/207 frames
```

**結論**: 
- Open3DのCUDAデバイスは初期化されているが、**実際の処理はCPUで実行されている**
- 深度データがあるため、MiDaS深度推定は使用されていない
- **現在、GPUはほとんど使用されていない**

## GPU使用率の確認方法

```bash
# プロセスごとのGPU使用状況
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# リアルタイム監視
watch -n 1 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv && echo "" && nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv'
```

## 改善の方向性

1. **深度推定を強制的に使用**: Depthデータがあっても、MiDaSで再推定して品質向上
2. **Open3D Tensor APIの完全実装**: TSDF統合をGPUで実行
3. **点群・メッシュ処理のGPU化**: Tensor APIを完全に活用

