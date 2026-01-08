# WSLでのGPU使用率監視方法

## プロセスごとのGPU使用率を確認する方法

### 方法1: nvidia-smi --query-compute-apps（推奨）

```bash
# プロセスごとのGPU使用状況
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv

# より詳細な情報
nvidia-smi --query-compute-apps=pid,process_name,used_memory,compute_instance_id,shared_memory_usage --format=csv
```

### 方法2: nvidia-smi pmon（プロセスモニター）

```bash
# 1秒ごとに更新（Ctrl+Cで終了）
nvidia-smi pmon -c 1

# 継続的に監視
nvidia-smi pmon
```

### 方法3: 監視スクリプトを使用

```bash
# 一度だけ表示
./monitor_gpu.sh

# リアルタイム監視
./gpu_monitor.sh
```

### 方法4: watchコマンドで継続監視

```bash
# 1秒ごとに更新
watch -n 1 'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv'

# より詳細な情報
watch -n 1 'nvidia-smi --query-compute-apps=pid,process_name,used_memory,compute_instance_id --format=csv && echo "" && nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv'
```

### 方法5: 特定のプロセスのGPU使用状況

```bash
# PythonプロセスのPIDを取得
ps aux | grep python | grep main.py

# 特定のPIDのGPU使用状況を確認
PID=12345  # 実際のPIDに置き換え
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv | grep "$PID"
```

## よく使うコマンド

### GPU全体の使用状況

```bash
nvidia-smi
```

### GPU使用率のみ

```bash
nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv
```

### メモリ使用状況

```bash
nvidia-smi --query-gpu=memory.used,memory.total,memory.free --format=csv
```

### プロセスとGPU使用状況を同時に表示

```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv && \
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv
```

## 注意点

- `nvidia-smi --query-compute-apps`は、**現在GPUを使用しているプロセスのみ**を表示します
- CPUで実行されているプロセスは表示されません
- Open3DのTSDF統合はCPUで実行されるため、GPU使用プロセスとして表示されない場合があります
- PyTorch（MiDaS深度推定）はGPUを使用するため、表示されます

## 実用的な監視コマンド

### リアルタイム監視（推奨）

```bash
watch -n 1 'echo "=== GPU Processes ==="; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null || echo "No GPU processes"; echo ""; echo "=== GPU Status ==="; nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv'
```

### ログファイルに記録

```bash
# ログファイルに記録しながら監視
watch -n 1 'date && nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv && nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv' | tee gpu_usage.log
```

