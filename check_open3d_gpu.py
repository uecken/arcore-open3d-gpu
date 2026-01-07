#!/usr/bin/env python3
"""
Open3DのGPU対応状況を確認するスクリプト
"""

import sys

try:
    import open3d as o3d
    print(f"Open3D version: {o3d.__version__}")
    
    # Open3Dのバージョン確認
    version_parts = o3d.__version__.split('.')
    major = int(version_parts[0])
    minor = int(version_parts[1])
    
    print(f"\n=== Open3D GPU対応状況 ===")
    
    # 0.19以降でSYCLバックエンドが利用可能
    if major > 0 or (major == 0 and minor >= 19):
        print("✓ Open3D 0.19以降: SYCLバックエンドによるGPUサポートが利用可能")
        
        # o3d.core.Deviceが利用可能か確認
        if hasattr(o3d, 'core') and hasattr(o3d.core, 'Device'):
            print("✓ o3d.core.Device APIが利用可能")
            
            # デバイス一覧を取得
            try:
                devices = o3d.core.Device.get_available_devices()
                print(f"  利用可能なデバイス: {devices}")
                
                # CUDAデバイスを確認
                cuda_devices = [d for d in devices if 'CUDA' in str(d)]
                if cuda_devices:
                    print(f"  CUDAデバイス: {cuda_devices}")
                else:
                    print("  CUDAデバイス: 見つかりませんでした")
            except Exception as e:
                print(f"  デバイス情報の取得に失敗: {e}")
        else:
            print("✗ o3d.core.Device APIが利用できません")
    else:
        print("✗ Open3D 0.19未満: GPUサポートは限定的")
    
    # TSDF Volume統合のGPU対応
    print(f"\n=== TSDF Volume統合のGPU対応 ===")
    print("注意: ScalableTSDFVolumeは現在のバージョンではCPUで実行されます")
    print("GPU対応には、Open3Dの新しいTensor APIを使用する必要があります")
    
    # CUDAの利用可能性を確認
    print(f"\n=== CUDA環境 ===")
    try:
        import torch
        if torch.cuda.is_available():
            print(f"✓ PyTorch CUDA: 利用可能")
            print(f"  CUDAデバイス数: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"  Device {i}: {torch.cuda.get_device_name(i)}")
        else:
            print("✗ PyTorch CUDA: 利用不可")
    except ImportError:
        print("✗ PyTorch: インストールされていません")
    
    print(f"\n=== 結論 ===")
    print("現在のコードでは、Open3DのTSDF統合処理はCPUで実行されています。")
    print("GPU対応を追加するには、Open3Dの新しいTensor APIを使用する必要があります。")
    
except ImportError as e:
    print(f"エラー: Open3Dがインストールされていません: {e}")
    sys.exit(1)
except Exception as e:
    print(f"エラー: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

