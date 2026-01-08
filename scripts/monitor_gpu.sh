#!/bin/bash
# GPU使用率を監視するスクリプト（プロセスごと）

echo "=== GPU使用状況（プロセスごと）==="
echo ""

# 方法1: nvidia-smiでプロセス情報を取得
echo "【方法1: nvidia-smi --query-compute-apps】"
nvidia-smi --query-compute-apps=pid,process_name,used_memory,compute_instance_id --format=csv 2>/dev/null || echo "No compute processes found"

echo ""
echo "【方法2: nvidia-smi pmon（プロセスモニター）】"
echo "Press Ctrl+C to stop"
nvidia-smi pmon -c 1 2>/dev/null || echo "pmon not available, using alternative method"

echo ""
echo "【方法3: 詳細なGPU情報】"
nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,memory.free --format=csv

echo ""
echo "【方法4: 全プロセス情報（テーブル形式）】"
nvidia-smi

echo ""
echo "【方法5: 特定のプロセスを監視】"
echo "PythonプロセスのGPU使用状況:"
ps aux | grep python | grep -v grep | awk '{print $2}' | while read pid; do
    echo "PID: $pid"
    nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null | grep "$pid" || echo "  Not using GPU"
done

