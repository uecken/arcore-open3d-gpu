#!/usr/bin/env python3
"""
MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())
MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())

MVS（COLMAP）パイプラインのテストスクリプト
COLMAPのインストール確認と基本的な機能テスト
"""

import sys
from pathlib import Path
import yaml

# パスを追加
sys.path.insert(0, str(Path(__file__).parent))

from utils.arcore_parser import ARCoreDataParser
from pipeline.colmap_mvs import COLMAPMVSPipeline

def test_colmap_availability():
    """COLMAPのインストール確認"""
    print("=" * 60)
    print("Test 1: COLMAP Availability Check")
    print("=" * 60)
    
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    result = pipeline.check_colmap_available()
    
    if result:
        print("✓ COLMAP is available")
        return True
    else:
        print("✗ COLMAP is not available")
        print("  Install COLMAP: sudo apt-get install colmap")
        return False

def test_colmap_model_creation():
    """COLMAPモデル作成のテスト（小さなデータセットで）"""
    print("\n" + "=" * 60)
    print("Test 2: COLMAP Model Creation Test")
    print("=" * 60)
    
    # 既存のセッションを探す
    sessions_dir = Path("data/sessions")
    if not sessions_dir.exists():
        print("✗ Sessions directory not found")
        return False
    
    # 最初のセッションを使用
    sessions = [d for d in sessions_dir.iterdir() if d.is_dir()]
    if not sessions:
        print("✗ No sessions found")
        return False
    
    test_session = sessions[0]
    print(f"Using session: {test_session.name}")
    
    # パーサーでデータを読み込む
    parser = ARCoreDataParser(test_session)
    if not parser.parse():
        print("✗ Failed to parse session data")
        return False
    
    print(f"✓ Parsed {len(parser.frames)} frames")
    
    if not parser.intrinsics:
        print("✗ Camera intrinsics not found")
        return False
    
    print(f"✓ Camera intrinsics: fx={parser.intrinsics.fx:.2f}, fy={parser.intrinsics.fy:.2f}")
    
    # COLMAPモデル作成をテスト
    config = yaml.safe_load(open('config.yaml'))
    gpu_config = config.get('gpu', {})
    pipeline = COLMAPMVSPipeline(config, gpu_config)
    
    colmap_dir = test_session / "colmap_test"
    colmap_dir.mkdir(exist_ok=True)
    
    print(f"Creating COLMAP model in: {colmap_dir}")
    
    try:
        result = pipeline.create_colmap_model_from_arcore_poses(
            parser,
            colmap_dir,
            lambda p, m: print(f"  Progress: {p}% - {m}")
        )
        
        if result:
            print("✓ COLMAP model created successfully")
            
            # ファイルの確認
            sparse_dir = colmap_dir / "sparse" / "0"
            cameras_file = sparse_dir / "cameras.txt"
            images_file = sparse_dir / "images.txt"
            points_file = sparse_dir / "points3D.txt"
            
            if cameras_file.exists():
                print(f"✓ cameras.txt created: {cameras_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(cameras_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for line in lines[:3]:
                        print(f"    {line.strip()}")
            
            if images_file.exists():
                print(f"✓ images.txt created: {images_file.stat().st_size} bytes")
                # 最初の数行を表示
                with open(images_file) as f:
                    lines = f.readlines()
                    print(f"  First lines:")
                    for i, line in enumerate(lines[:5]):
                        print(f"    {line.strip()}")
                        if i == 4:
                            break
            
            if points_file.exists():
                print(f"✓ points3D.txt created: {points_file.stat().st_size} bytes")
            
            return True
        else:
            print("✗ Failed to create COLMAP model")
            return False
            
    except Exception as e:
        print(f"✗ Error creating COLMAP model: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """メインテスト実行"""
    print("MVS (COLMAP) Pipeline Test")
    print("=" * 60)
    
    # Test 1: COLMAPのインストール確認
    colmap_available = test_colmap_availability()
    
    # Test 2: COLMAPモデル作成のテスト（COLMAPがなくてもファイル作成はテスト可能）
    # 注意: 実際のCOLMAPコマンド実行にはCOLMAPが必要だが、
    # ARCoreポーズからCOLMAPモデルファイルを作成する部分はテスト可能
    print("\nNote: Model file creation test will run even without COLMAP installed")
    model_created = test_colmap_model_creation()
    
    # 結果サマリー
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"COLMAP available: {'✓' if colmap_available else '✗'}")
    print(f"Model creation: {'✓' if model_created else '✗'}")
    
    if colmap_available and model_created:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Update config.yaml: processing.default_mode = 'mvs'")
        print("2. Test with a real job using reprocess_job.py")
        return 0
    elif colmap_available:
        print("\n⚠ COLMAP is available but model creation failed")
        print("Check the error messages above")
        return 1
    else:
        print("\n⚠ COLMAP is not installed")
        print("Install COLMAP: sudo apt-get install colmap")
        return 1

if __name__ == "__main__":
    sys.exit(main())