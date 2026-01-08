#!/bin/bash
# GPU使用率をリアルタイムで監視するスクリプト（プロセスごと）

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== GPU使用状況監視（プロセスごと）===${NC}"
echo ""

# 方法1: プロセスごとのGPU使用状況
echo -e "${GREEN}【プロセスごとのGPU使用状況】${NC}"
nvidia-smi --query-compute-apps=pid,process_name,used_memory,compute_instance_id --format=csv 2>/dev/null
if [ $? -ne 0 ] || [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | grep -v '^$')" ]; then
    echo "現在GPUを使用しているプロセスはありません"
fi

echo ""
echo -e "${GREEN}【GPU全体の使用状況】${NC}"
nvidia-smi --query-gpu=index,name,utilization.gpu,utilization.memory,memory.used,memory.total,memory.free --format=csv

echo ""
echo -e "${GREEN}【Pythonプロセスの詳細】${NC}"
ps aux | grep -E "python.*main\.py|uvicorn.*main" | grep -v grep | while read line; do
    pid=$(echo $line | awk '{print $2}')
    cmd=$(echo $line | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
    mem=$(echo $line | awk '{print $6/1024 " MB"}')
    cpu=$(echo $line | awk '{print $3 "%"}')
    
    echo "PID: $pid | CPU: $cpu | Memory: $mem"
    echo "  Command: $cmd"
    
    # このプロセスがGPUを使用しているか確認
    gpu_usage=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | grep "^$pid," | awk -F',' '{print $2}')
    if [ -n "$gpu_usage" ]; then
        echo -e "  ${YELLOW}GPU Memory: $gpu_usage${NC}"
    else
        echo "  GPU Memory: Not using GPU"
    fi
    echo ""
done

echo -e "${BLUE}=== リアルタイム監視（Ctrl+Cで終了）===${NC}"
echo "1秒ごとに更新されます..."
echo ""

# リアルタイム監視
watch -n 1 'echo "=== GPU Processes ==="; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv 2>/dev/null || echo "No GPU processes"; echo ""; echo "=== GPU Status ==="; nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total --format=csv'

