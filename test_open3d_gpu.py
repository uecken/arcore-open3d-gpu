#!/usr/bin/env python3
"""Open3D GPU対応のテスト"""

import open3d as o3d
import torch

print(f"Open3D version: {o3d.__version__}")
print(f"PyTorch CUDA available: {torch.cuda.is_available()}")

# Open3Dのデバイス作成をテスト
try:
    # CPUデバイス
    cpu_device = o3d.core.Device("CPU:0")
    print(f"✓ CPU device: {cpu_device}")
    print(f"  Device type: {cpu_device.get_type()}")
    print(f"  Device ID: {cpu_device.get_id()}")
except Exception as e:
    print(f"✗ CPU device error: {e}")

# CUDAデバイスのテスト
if torch.cuda.is_available():
    try:
        cuda_device = o3d.core.Device("CUDA:0")
        print(f"✓ CUDA device: {cuda_device}")
        print(f"  Device type: {cuda_device.get_type()}")
        print(f"  Device ID: {cuda_device.get_id()}")
    except Exception as e:
        print(f"✗ CUDA device error: {e}")
        print("  Note: Open3D may not have CUDA support compiled")
else:
    print("⚠ PyTorch CUDA not available")

