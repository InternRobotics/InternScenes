"""USD to point-cloud conversion."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import open3d as o3d

from .prim_utils import recursive_parse
from .stage_utils import get_all_mesh_prims, remove_empty_xform


@dataclass
class RawScenePCD:
    pcd: o3d.geometry.PointCloud


def get_mesh_from_points_and_faces(
    points: list,
    face_vertex_counts: list[int],
    face_vertex_indices: list[int],
) -> o3d.geometry.TriangleMesh:
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(points)
    triangles = []
    cursor = 0
    for count in face_vertex_counts:
        if count == 3:
            triangles.append(face_vertex_indices[cursor:cursor + 3])
        cursor += count
    mesh.triangles = o3d.utility.Vector3iVector(triangles)
    mesh.compute_vertex_normals()
    return mesh


def sample_points_from_mesh(
    mesh: o3d.geometry.TriangleMesh,
    num_points: int = 1000,
) -> o3d.geometry.PointCloud:
    return mesh.sample_points_uniformly(number_of_points=num_points)


def sample_points_from_prim(prim, num_points: int = 1000) -> tuple[np.ndarray, o3d.geometry.TriangleMesh]:
    points, face_counts, face_indices = recursive_parse(prim)
    mesh = get_mesh_from_points_and_faces(points, face_counts, face_indices)
    pcd = sample_points_from_mesh(mesh, num_points)
    return np.asarray(pcd.points), mesh


def usd2pcd(stage, valid_prim_paths: set[str] | None = None) -> RawScenePCD:
    meters_per_unit = stage.GetMetadata("metersPerUnit") or 1.0
    stage = remove_empty_xform(stage)
    mesh_prims = get_all_mesh_prims(stage)

    prim_points = []
    skipped = 0
    for prim in mesh_prims:
        path = str(prim.GetPath())
        if valid_prim_paths is not None and path not in valid_prim_paths:
            skipped += 1
            continue
        try:
            points, mesh = sample_points_from_prim(prim, num_points=10000)
        except RuntimeError:
            skipped += 1
            continue
        del mesh
        prim_points.append(points * meters_per_unit)

    if skipped:
        print(f"[usd2pcd] skipped {skipped} prim(s)")
    if not prim_points:
        raise RuntimeError("usd2pcd: no mesh geometry found")

    all_points = np.concatenate(prim_points, axis=0)
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(all_points)
    return RawScenePCD(pcd=pcd)
