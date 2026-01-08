# メモリ使用量調査結果

## 問題の原因

**GPUメモリではなく、システムRAM（メインメモリ）の不足が原因です。**

### 調査結果

1. **OOM Killerのログ**:
   ```
   Out of memory: Killed process 5752 (python) 
   total-vm:81811156kB, anon-rss:20242296kB
   ```
   - プロセスが約**20GBのRAM**を使用していた
   - これはGPUメモリではなく、システムRAM

2. **現在のメモリ使用状況**:
   - 元のサーバー（port 8001）: 約**16GBのRAM**を使用
   - GPU対応版サーバー（port 8002）: 約**20GBのRAM**を使用（統合中）
   - **合計約36GB**のRAMが必要だが、システムは31GBしかない

3. **GPUメモリ**:
   - Windows側で確認した通り、GPUメモリは問題なし
   - 問題はシステムRAM

## 解決方法

### 1. 他のサーバーを停止（推奨）

元のサーバー（port 8001）が16GBのメモリを使用しているため、停止する：

```bash
# 元のサーバーのプロセスを確認
ps aux | grep "uvicorn.*main.*8001"

# 停止
kill <PID>
```

### 2. Volumeの明示的な解放

統合後にVolumeを解放する処理を追加済み：

```python
# Volumeを明示的に解放
integration.volume = None
import gc
gc.collect()
```

### 3. voxel_lengthの調整

メモリが限られている場合、`voxel_length`を大きくする：

```yaml
processing:
  tsdf:
    voxel_length: 0.01         # 10mm（低メモリ使用量）
    # voxel_length: 0.005      # 5mm（標準）
    # voxel_length: 0.003      # 3mm（高メモリ使用量、非推奨）
```

### 4. メモリ使用量の監視

処理中にメモリ使用量を監視：

```bash
# 別のターミナルで実行
watch -n 1 'free -h && echo "---" && ps aux --sort=-%mem | head -5'
```

### 5. Swap領域の増加（一時的な解決策）

```bash
# Swap領域を確認
swapon --show

# Swap領域を増やす（必要に応じて）
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 推奨アクション

1. **即座に実行**: 元のサーバー（port 8001）を停止
2. **設定調整**: `voxel_length: 0.01`に変更してテスト
3. **メモリ監視**: 処理中にメモリ使用量を監視

## メモリ使用量の目安

- `voxel_length: 0.003` (3mm): 約20-30GB RAM（非推奨）
- `voxel_length: 0.005` (5mm): 約10-15GB RAM
- `voxel_length: 0.01` (10mm): 約2-4GB RAM（推奨、メモリが限られている場合）

*実際の使用量はシーンのサイズとフレーム数によって異なります。

