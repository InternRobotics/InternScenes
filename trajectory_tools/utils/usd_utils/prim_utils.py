"""USD prim helpers used by trajectory generation and rendering."""

from __future__ import annotations

from typing import Any

import numpy as np
from pxr import Gf, Usd, UsdGeom


def _to_list(data) -> list:
    return [] if data is None else [item for item in data]


def recursive_parse(prim: Usd.Prim) -> tuple[list[Gf.Vec3f], list[int], list[int]]:
    points_total = []
    face_counts_total = []
    face_indices_total = []

    if prim.IsA(UsdGeom.Mesh):
        imageable = UsdGeom.Imageable(prim)
        world_transform = np.array(
            imageable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        )

        points = np.array(_to_list(prim.GetAttribute("points").Get()))
        face_counts = _to_list(prim.GetAttribute("faceVertexCounts").Get())
        face_indices = _to_list(prim.GetAttribute("faceVertexIndices").Get())

        points_h = np.hstack([points, np.ones((points.shape[0], 1))])
        transformed_h = np.dot(points_h, world_transform)
        points = transformed_h[:, :3] / transformed_h[:, 3][:, np.newaxis]

        if np.isnan(points).any():
            valid_points = ~np.isnan(points).any(axis=1)
            points_clean = points[valid_points].tolist()
            face_indices_np = np.array(face_indices).reshape(-1, 3)
            old_to_new = np.full(points.shape[0], -1)
            old_to_new[valid_points] = np.arange(np.sum(valid_points))
            valid_faces = np.all(old_to_new[face_indices_np] != -1, axis=1)
            face_indices_clean = old_to_new[face_indices_np[valid_faces]].flatten().tolist()
            face_counts_clean = np.array(face_counts)[valid_faces].tolist()
            base_num = len(points_total)
            face_indices_total.extend((base_num + np.array(face_indices_clean)).tolist())
            face_counts_total.extend(face_counts_clean)
            points_total.extend(points_clean)
        else:
            base_num = len(points_total)
            face_indices_total.extend((base_num + np.array(face_indices)).tolist())
            face_counts_total.extend(face_counts)
            points_total.extend(points)

    for child in prim.GetChildren():
        child_points, child_counts, child_indices = recursive_parse(child)
        base_num = len(points_total)
        face_indices_total.extend((base_num + np.array(child_indices)).tolist())
        face_counts_total.extend(child_counts)
        points_total.extend(child_points)

    return points_total, face_counts_total, face_indices_total


def is_empty_xform(xform_prim: Usd.Prim) -> bool:
    assert xform_prim.IsA(UsdGeom.Xform)
    return len(xform_prim.GetChildren()) == 0


def is_mesh_xform(prim: Usd.Prim) -> bool:
    if prim.IsA(UsdGeom.Mesh):
        return True
    return any(is_mesh_xform(child) for child in prim.GetChildren())


def compute_bbox(prim: Usd.Prim) -> np.ndarray:
    imageable = UsdGeom.Imageable(prim)
    bound = imageable.ComputeWorldBound(Usd.TimeCode.Default(), UsdGeom.Tokens.default_)
    aligned = bound.ComputeAlignedBox()
    return np.array([aligned.min, aligned.max])


def set_prim_cast_shadow_true(prim: Usd.Prim) -> None:
    if not (prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Xform)):
        return
    for attr in prim.GetAttributes():
        if attr.GetName() == "primvars:doNotCastShadows":
            attr.Set(False)
            return
    for child in prim.GetChildren():
        set_prim_cast_shadow_true(child)


def get_all_light_prims(stage: Usd.Stage) -> list[Usd.Prim]:
    light_types = {"DistantLight", "SphereLight", "DiskLight", "RectLight", "CylinderLight"}
    return [prim for prim in stage.Traverse() if prim.GetTypeName() in light_types]


def randomize_single_light_attributes(light_prim: Usd.Prim) -> dict[str, Any]:
    scale = float(np.random.uniform(0.5, 1.5))
    color_temperature = float(np.random.normal(4500, 1500))
    intensity = float(np.random.normal(25000, 5000))
    color = tuple(float(v) for v in np.random.uniform(0.1, 0.9, size=3))

    light_prim.GetAttribute("xformOp:scale").Set((scale, scale, scale))
    light_prim.GetAttribute("inputs:colorTemperature").Set(color_temperature)
    light_prim.GetAttribute("inputs:enableColorTemperature").Set(True)
    light_prim.GetAttribute("inputs:intensity").Set(intensity)
    light_prim.GetAttribute("inputs:color").Set(color)
    return {
        "scale": scale,
        "colorTemperature": color_temperature,
        "intensity": intensity,
        "color": color,
    }


def randomize_all_light_attributes(stage: Usd.Stage) -> dict[str, Any]:
    return {
        str(light_prim.GetPath()): randomize_single_light_attributes(light_prim)
        for light_prim in get_all_light_prims(stage)
    }


IsEmptyXform = is_empty_xform
IsMeshXform = is_mesh_xform
