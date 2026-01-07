#!/usr/bin/env python3
"""
既存のメッシュファイルを簡略化し、ASCII形式で再保存するスクリプト
Three.jsのPLYLoaderと互換性がある形式で保存します
"""

import sys
import open3d as o3d
from pathlib import Path

def fix_mesh(job_id: str, max_triangles: int = 500000):
    """メッシュを簡略化してASCII形式で保存"""
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
    
    # 簡略化
    if original_triangles > max_triangles:
        print(f"Simplifying mesh to {max_triangles} triangles...")
        simplified = mesh.simplify_quadric_decimation(max_triangles)
        
        if len(simplified.triangles) == 0:
            print("Error: Simplification failed, mesh has no triangles after simplification!")
            return False
        
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
        sys.exit(1)
    
    job_id = sys.argv[1]
    max_triangles = int(sys.argv[2]) if len(sys.argv) > 2 else 500000
    
    success = fix_mesh(job_id, max_triangles)
    sys.exit(0 if success else 1)

