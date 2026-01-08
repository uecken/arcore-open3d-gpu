#!/usr/bin/env python3
"""
メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

メッシュ表示ツール
Open3Dを使用してPLYメッシュファイルを表示
"""

import sys
import os
import argparse
from pathlib import Path

# 仮想環境のパスを確認
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PATHS = [
    SCRIPT_DIR / "venv",
    SCRIPT_DIR / ".venv",
    Path("/opt/arcore-open3d/venv"),  # 元のプロジェクトの仮想環境
]

# 仮想環境が見つかった場合は警告を表示
venv_found = False
for venv_path in VENV_PATHS:
    if venv_path.exists():
        venv_found = True
        print(f"⚠ 仮想環境が見つかりました: {venv_path}")
        print(f"   以下のコマンドで仮想環境を有効化してください:")
        print(f"   source {venv_path}/bin/activate")
        print()
        break

try:
    import open3d as o3d
    import numpy as np
except ImportError as e:
    if venv_found:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化してから実行してください:")
        print(f"   source {VENV_PATHS[0]}/bin/activate")
        print(f"   python view_mesh.py ...")
    else:
        print(f"❌ エラー: Open3Dがインストールされていません")
        print(f"   仮想環境を有効化するか、Open3Dをインストールしてください")
    sys.exit(1)


def get_mesh_info(mesh: o3d.geometry.TriangleMesh) -> dict:
    """メッシュの情報を取得"""
    return {
        'vertices': len(mesh.vertices),
        'triangles': len(mesh.triangles),
        'has_normals': mesh.has_vertex_normals(),
        'has_colors': mesh.has_vertex_colors(),
        'is_watertight': mesh.is_watertight(),
        'is_edge_manifold': mesh.is_edge_manifold(allow_boundary_edges=True),
        'is_vertex_manifold': mesh.is_vertex_manifold(),
    }


def print_mesh_info(mesh: o3d.geometry.TriangleMesh, file_path: Path):
    """メッシュ情報を表示"""
    info = get_mesh_info(mesh)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print("=" * 60)
    print("メッシュ情報")
    print("=" * 60)
    print(f"ファイル: {file_path}")
    print(f"ファイルサイズ: {file_size_mb:.2f} MB")
    print(f"頂点数: {info['vertices']:,}")
    print(f"三角形数: {info['triangles']:,}")
    print(f"法線: {'あり' if info['has_normals'] else 'なし'}")
    print(f"色: {'あり' if info['has_colors'] else 'なし'}")
    print(f"Watertight: {'はい' if info['is_watertight'] else 'いいえ'}")
    print(f"Edge Manifold: {'はい' if info['is_edge_manifold'] else 'いいえ'}")
    print(f"Vertex Manifold: {'はい' if info['is_vertex_manifold'] else 'いいえ'}")
    
    # バウンディングボックス情報
    bbox = mesh.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    center = bbox.get_center()
    print(f"\nバウンディングボックス:")
    print(f"  中心: ({center[0]:.3f}, {center[1]:.3f}, {center[2]:.3f})")
    print(f"  サイズ: ({extent[0]:.3f}, {extent[1]:.3f}, {extent[2]:.3f})")
    print("=" * 60)


def view_mesh(mesh_path: Path, window_name: str = "Mesh Viewer"):
    """メッシュを表示"""
    print(f"メッシュを読み込んでいます: {mesh_path}")
    
    if not mesh_path.exists():
        print(f"エラー: ファイルが見つかりません: {mesh_path}")
        return False
    
    try:
        # メッシュを読み込む
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        
        if len(mesh.vertices) == 0:
            print("エラー: メッシュに頂点がありません")
            return False
        
        if len(mesh.triangles) == 0:
            print("エラー: メッシュに三角形がありません")
            return False
        
        # メッシュ情報を表示
        print_mesh_info(mesh, mesh_path)
        
        # 法線がない場合は計算
        if not mesh.has_vertex_normals():
            print("\n法線を計算しています...")
            mesh.compute_vertex_normals()
        
        # 色がない場合は追加（高さベースの色）
        if not mesh.has_vertex_colors():
            print("色を追加しています（高さベース）...")
            vertices = np.asarray(mesh.vertices)
            if len(vertices) > 0:
                z_min = vertices[:, 2].min()
                z_max = vertices[:, 2].max()
                if z_max > z_min:
                    z_normalized = (vertices[:, 2] - z_min) / (z_max - z_min)
                    colors = np.zeros((len(vertices), 3))
                    colors[:, 0] = np.clip(2 * (1 - z_normalized), 0, 1)  # Red
                    colors[:, 1] = np.clip(2 * z_normalized if z_normalized < 0.5 else 2 * (1 - z_normalized), 0, 1)  # Green
                    colors[:, 2] = np.clip(2 * z_normalized - 1, 0, 1)  # Blue
                    mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
                else:
                    mesh.paint_uniform_color([0.7, 0.7, 0.7])
            else:
                mesh.paint_uniform_color([0.7, 0.7, 0.7])
        
        # メッシュを中心に移動
        mesh.translate(-mesh.get_center())
        
        print("\nメッシュを表示しています...")
        print("操作方法:")
        print("  - マウス左ドラッグ: 回転")
        print("  - マウス右ドラッグ: 平行移動")
        print("  - マウスホイール: ズーム")
        print("  - 'Q' または 'Esc': 終了")
        print("  - 'R': リセット")
        print("  - 'W': ワイヤーフレーム表示切り替え")
        print("  - 'L': ライティング切り替え")
        print("  - 'P': 点群表示切り替え")
        print()
        
        # 可視化
        o3d.visualization.draw_geometries(
            [mesh],
            window_name=window_name,
            width=1920,
            height=1080,
            point_show_normal=False,
            mesh_show_wireframe=False,
            mesh_show_back_face=False
        )
        
        return True
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Open3Dを使用してPLYメッシュファイルを表示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # ジョブIDを指定して表示
  python view_mesh.py 6d7cd464
  
  # ファイルパスを直接指定
  python view_mesh.py data/results/6d7cd464/mesh.ply
  
  # 元のメッシュ（簡略化前）を表示
  python view_mesh.py 6d7cd464 --original
        """
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='ジョブIDまたはメッシュファイルのパス'
    )
    
    parser.add_argument(
        '--original',
        action='store_true',
        help='元のメッシュ（mesh_original.ply）を表示（簡略化前）'
    )
    
    parser.add_argument(
        '--results-dir',
        type=str,
        default='/opt/arcore-open3d-gpu/data/results',
        help='結果ディレクトリのパス（デフォルト: /opt/arcore-open3d-gpu/data/results）'
    )
    
    args = parser.parse_args()
    
    # 入力パスの処理
    input_path = Path(args.input)
    
    # ファイルパスかジョブIDかを判定
    if input_path.exists() and input_path.is_file():
        # ファイルパスが指定された場合
        mesh_path = input_path
    else:
        # ジョブIDが指定された場合
        results_dir = Path(args.results_dir)
        job_id = args.input
        
        if args.original:
            mesh_path = results_dir / job_id / "mesh_original.ply"
        else:
            mesh_path = results_dir / job_id / "mesh.ply"
    
    # メッシュを表示
    success = view_mesh(mesh_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()