"""Minimal Isaac Sim scene and camera setup helpers."""

from __future__ import annotations

import numpy as np
import omni
from omni.isaac.core import World
from omni.isaac.core.utils.semantics import add_update_semantics
from omni.isaac.core.utils.stage import add_reference_to_stage
from omni.isaac.sensor import Camera
from pxr import Usd

from utils.usd_utils.mdl_utils import fix_mdls
from utils.usd_utils.prim_utils import set_prim_cast_shadow_true
from utils.usd_utils.stage_utils import (
    get_all_mesh_prims_from_scope,
    switch_all_lights,
)


def init_world(
    stage_units_in_meters: float = 1.0,
    physics_dt: float = 0.01,
    rendering_dt: float = 0.01,
) -> World:
    world = World(
        stage_units_in_meters=stage_units_in_meters,
        physics_dt=physics_dt,
        rendering_dt=rendering_dt,
    )
    world.reset()
    return world


def load_scene_to_world(
    scene_usd_path: str,
    default_mdl_path: str,
) -> tuple[World, Usd.Stage, float]:
    usd_scene_stage = Usd.Stage.Open(scene_usd_path)
    meters_per_unit = usd_scene_stage.GetMetadata("metersPerUnit") or 1.0
    world = init_world()
    fix_mdls(scene_usd_path, default_mdl_path)
    add_reference_to_stage(scene_usd_path, "/World/scene")
    stage = omni.usd.get_context().get_stage()
    switch_all_lights(stage, "on")
    return world, stage, meters_per_unit


def setup_instance_scene_copy(stage: Usd.Stage) -> None:
    mesh_prims = (
        get_all_mesh_prims_from_scope(stage, "scene/Instances")
        + get_all_mesh_prims_from_scope(stage, "scene/Structure")
    )
    for prim in mesh_prims:
        set_prim_cast_shadow_true(prim)
        add_update_semantics(prim, semantic_label=prim.GetName(), type_label="class")


def init_camera(
    camera_name: str = "camera",
    image_width: int = 640,
    image_height: int = 480,
    position: np.ndarray = np.array([0.0, 0.0, 0.0]),
    orientation: np.ndarray = np.array([0.0, 0.0, 0.0, 1.0]),
) -> Camera:
    return Camera(
        prim_path=f"/World/{camera_name}",
        resolution=(image_width, image_height),
        position=position,
        orientation=orientation,
    )


def setup_camera(
    camera: Camera,
    focal_length: float = 18.0,
    clipping_range_min: float = 0.01,
    clipping_range_max: float = 1000000.0,
    vertical_aperture: float = 15.2908,
    horizontal_aperture: float = 20.0955,
    with_distance: bool = True,
    with_semantic: bool = False,
    panorama: bool = False,
) -> None:
    camera.initialize()
    camera.set_focal_length(focal_length)
    camera.set_clipping_range(clipping_range_min, clipping_range_max)
    camera.set_vertical_aperture(vertical_aperture)
    camera.set_horizontal_aperture(horizontal_aperture)
    if with_distance:
        camera.add_distance_to_image_plane_to_frame()
    if with_semantic:
        camera.add_semantic_segmentation_to_frame()
    if panorama:
        camera.set_projection_type("fisheyeSpherical")
        camera.remove_distance_to_image_plane_from_frame()
        camera.add_distance_to_camera_to_frame()


def get_depth_to_camera(camera: Camera) -> np.ndarray | None:
    depth = camera._custom_annotators["distance_to_camera"].get_data()
    return depth if isinstance(depth, np.ndarray) and depth.size > 0 else None


def _get_object_mask(camera: Camera) -> dict | None:
    annotator = camera._custom_annotators["semantic_segmentation"]
    annotation = annotator.get_data()
    mask = annotation["data"]
    id_to_labels = annotation["info"]["idToLabels"]
    if isinstance(mask, np.ndarray) and mask.size > 0:
        return {"mask": mask.astype(np.int32), "id2labels": id_to_labels}
    return None


def get_src(camera: Camera, render_type: str) -> np.ndarray | dict | None:
    if render_type == "seg":
        return _get_object_mask(camera)
    raise ValueError(f"Unsupported camera source: {render_type}")
