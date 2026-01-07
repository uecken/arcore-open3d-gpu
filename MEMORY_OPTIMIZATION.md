# メモリ最適化ガイド

## 問題: "Killed" エラー

プロセスが「Killed」で終了する場合、メモリ不足（OOM Killer）が原因です。

## 原因

TSDF Volumeの`voxel_length`が小さすぎると、メモリ使用量が指数関数的に増加します：

- `voxel_length: 0.003` (3mm) → 非常に高メモリ使用量
- `voxel_length: 0.005` (5mm) → 推奨値
- `voxel_length: 0.01` (10mm) → 低メモリ使用量

## 解決方法

### 1. voxel_lengthを調整

`config.yaml`で`voxel_length`を調整：

```yaml
processing:
  tsdf:
    voxel_length: 0.005        # 5mm（推奨）
    # voxel_length: 0.003      # 3mm（高メモリ使用量、非推奨）
    # voxel_length: 0.01       # 10mm（低メモリ使用量、低解像度）
```

### 2. メモリ使用量の監視

処理中にメモリ使用量を監視：

```bash
# 別のターミナルで実行
watch -n 1 free -h
# または
watch -n 1 nvidia-smi
```

### 3. バッチ処理のサイズを調整

大量のフレームを処理する場合、バッチサイズを小さくする：

```python
# フレームを分割して処理
frames_batch = frames[:50]  # 50フレームずつ処理
```

### 4. システムメモリの確認

```bash
free -h
```

利用可能メモリが少ない場合、他のプロセスを終了するか、swap領域を増やす。

## 推奨設定

### 標準的な設定（バランス型）

```yaml
processing:
  tsdf:
    voxel_length: 0.005        # 5mm
    sdf_trunc: 0.04            # 8倍
```

### 高解像度が必要な場合

```yaml
processing:
  tsdf:
    voxel_length: 0.004        # 4mm（メモリに余裕がある場合のみ）
    sdf_trunc: 0.032            # 8倍
```

### メモリが限られている場合

```yaml
processing:
  tsdf:
    voxel_length: 0.01         # 10mm
    sdf_trunc: 0.08            # 8倍
```

## メモリ使用量の目安

- `voxel_length: 0.003` (3mm): 約8-16GB RAM
- `voxel_length: 0.005` (5mm): 約2-4GB RAM
- `voxel_length: 0.01` (10mm): 約0.5-1GB RAM

*実際の使用量はシーンのサイズとフレーム数によって異なります。

