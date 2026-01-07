#!/usr/bin/env python3
"""
既存のメッシュファイルを簡略化し、ASCII形式で再保存するスクリプト
Three.jsのPLYLoaderと互換性がある形式で保存します
（regenerate_mesh.pyを使用することを推奨）
"""

import sys
import yaml
import open3d as o3d
from pathlib import Path
from typing import Dict, Any

# 設定読み込み
CONFIG_PATH = Path(__file__).parent / "config.yaml"

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {}

def fix_mesh(job_id: str, max_triangles: int = None):
    """メッシュを簡略化してASCII形式で保存（yaml設定を適用）"""
    config = load_config()
    
    results_dir = Path("/opt/arcore-open3d-gpu/data/results")
    mesh_path = results_dir / job_id / "mesh.ply"
    
    if not mesh_path.exists():
        print(f"Error: Mesh file not found: {mesh_path}")
        return False
    
    print(f"Reading mesh from: {mesh_path}")
    mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    
    original_triangles = len(mesh.triangles)
    print(f"Original mesh: {len(mesh.vertices)} vertices, {original_triangles} triangles")
    
    if original_triangles == 0:
        print("Error: Mesh has no triangles!")
        return False
    
    # 品質向上処理（yaml設定を適用）
    from regenerate_mesh import improve_mesh_quality
    mesh = improve_mesh_quality(mesh, config, job_id)
    
    # 簡略化（設定でON/OFF可能）
    if max_triangles is None:
        output_config = config.get('output', {})
        mesh_output_config = output_config.get('mesh', {})
        simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)  # デフォルト: true
        max_triangles = mesh_output_config.get('max_triangles_for_viewer', 1000000)
    else:
        output_config = config.get('output', {})
        mesh_output_config = output_config.get('mesh', {})
        simplify_for_viewer = mesh_output_config.get('simplify_for_viewer', True)  # デフォルト: true
    
    # 簡略化する前に元のメッシュを保存
    original_mesh_path = results_dir / job_id / "mesh_original.ply"
    save_original = False
    
    if simplify_for_viewer and original_triangles > max_triangles:
        print(f"Simplifying mesh to {max_triangles} triangles...")
        # 簡略化前に元のメッシュを保存
        try:
            o3d.io.write_triangle_mesh(str(original_mesh_path), mesh, write_ascii=False, compressed=False)
            save_original = True
            print(f"✓ Saved original mesh (before simplification): {original_triangles} triangles")
        except Exception as e:
            print(f"⚠ Failed to save original mesh: {e}")
        
        simplified = mesh.simplify_quadric_decimation(max_triangles)
        
        if len(simplified.triangles) == 0:
            print("Error: Simplification failed, mesh has no triangles after simplification!")
            return False
        
        # 簡略化後もクリーンアップ
        simplified.remove_duplicated_triangles()
        simplified.remove_duplicated_vertices()
        simplified.remove_non_manifold_edges()
        simplified.compute_vertex_normals()
        
        print(f"Simplified mesh: {len(simplified.vertices)} vertices, {len(simplified.triangles)} triangles")
        mesh_to_save = simplified
    else:
        print("Mesh is small enough, no simplification needed")
        mesh_to_save = mesh
    
    # ASCII形式で保存
    print(f"Saving mesh in ASCII format to: {mesh_path}")
    try:
        o3d.io.write_triangle_mesh(
            str(mesh_path),
            mesh_to_save,
            write_ascii=True,
            compressed=False
        )
        print(f"✓ Mesh saved successfully in ASCII format")
        print(f"  Final: {len(mesh_to_save.vertices)} vertices, {len(mesh_to_save.triangles)} triangles")
        return True
    except Exception as e:
        print(f"Error saving mesh: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_mesh.py <job_id> [max_triangles]")
        print("Example: python fix_mesh.py 1611626e 500000")
        print("Note: Use regenerate_mesh.py for full regeneration with yaml settings")
        sys.exit(1)
    
    job_id = sys.argv[1]
    max_triangles = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    success = fix_mesh(job_id, max_triangles)
    sys.exit(0 if success else 1)

