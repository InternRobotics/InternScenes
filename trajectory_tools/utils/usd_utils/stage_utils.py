"""USD stage helpers."""

from __future__ import annotations

from pxr import Usd, UsdGeom

from .prim_utils import is_empty_xform, is_mesh_xform, set_prim_cast_shadow_true


def get_all_mesh_prims(stage: Usd.Stage, node_path: str = "/World") -> list[Usd.Prim]:
    root = stage.GetPrimAtPath(node_path)
    mesh_prims = []
    for prim in root.GetAllChildren():
        if prim.IsA(UsdGeom.Mesh):
            mesh_prims.append(prim)
        elif prim.IsA(UsdGeom.Xform) and not is_empty_xform(prim) and is_mesh_xform(prim):
            mesh_prims.append(prim)
        elif not prim.IsA(UsdGeom.Mesh) and not prim.IsA(UsdGeom.Xform):
            mesh_prims.extend(get_all_mesh_prims(stage, prim.GetPath().pathString))
    return mesh_prims


def get_all_mesh_prims_from_scope(stage: Usd.Stage, scope_name: str) -> list[Usd.Prim]:
    scope = stage.GetPrimAtPath(f"/World/{scope_name}")
    mesh_prims = []
    for child in scope.GetChildren():
        mesh_prims.extend(get_all_mesh_prims(stage, f"/World/{scope_name}/{child.GetName()}"))
    return mesh_prims


def remove_empty_xform(stage: Usd.Stage) -> Usd.Stage:
    xforms = [
        prim for prim in stage.Traverse()
        if prim.IsA(UsdGeom.Xform)
        and prim.GetPath() != "/World"
        and not prim.IsInstanceable()
    ]
    xforms.sort(key=lambda prim: len(prim.GetPath().pathString.split("/")), reverse=True)
    for prim in xforms:
        if is_empty_xform(prim):
            stage.RemovePrim(prim.GetPath())
    return stage


def switch_all_lights(stage: Usd.Stage, action: str = "on") -> None:
    if action not in {"on", "off"}:
        raise ValueError("action must be 'on' or 'off'")
    light_types = {"DistantLight", "SphereLight", "DiskLight", "RectLight", "CylinderLight"}
    for prim in stage.Traverse():
        if prim.GetTypeName() in light_types:
            imageable = UsdGeom.Imageable(prim)
            imageable.MakeVisible() if action == "on" else imageable.MakeInvisible()


def setup_all_prims_cast_shadow_true(stage: Usd.Stage) -> None:
    for prim in stage.Traverse():
        set_prim_cast_shadow_true(prim)
