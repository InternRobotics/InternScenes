"""Render one trajectory with the current Isaac Sim scene state."""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Any

import cv2
import imageio
import numpy as np
from omni.isaac.core import World
from omni.isaac.sensor import Camera
from pxr import Usd
from tqdm import tqdm

from utils.common_utils.images_utils import colorize_instances
from utils.common_utils.sim_utils import get_depth_to_camera, get_src, setup_instance_scene_copy
from utils.usd_utils.mdl_utils import set_all_material_to_default
from utils.usd_utils.stage_utils import setup_all_prims_cast_shadow_true

MATERIAL_OVERRIDE_TYPES = {"shading", "shading_randlight"}
SUPPORT_RENDER_TYPES = {
    "rgb",
    "rgbd",
    "depth",
    "instance",
    "shading",
    "shading_randlight",
}


def get_intrinsic_matrix(camera: Camera) -> np.ndarray:
    width, height = camera.get_resolution()
    focal_length = camera.get_focal_length()
    horizontal_aperture = camera.get_horizontal_aperture()
    vertical_aperture = camera.get_vertical_aperture()
    fx = width * focal_length / horizontal_aperture
    fy = height * focal_length / vertical_aperture
    return np.array([[fx, 0, width / 2], [0, fy, height / 2], [0, 0, 1]], dtype=np.float32)


def _process_camera_pose(camera_pose: list, meters_per_unit: float) -> tuple[np.ndarray, np.ndarray]:
    position = np.array(camera_pose[0], dtype=np.float64) / meters_per_unit
    rotation = np.array(camera_pose[1], dtype=np.float64)
    return position, rotation


def _setup_save_env(
    save_dir: Path,
    output_name: str,
    need_video_writer: bool,
    video_fps: int,
    video_quality: int,
) -> tuple[Path | dict[str, Path], Any | None]:
    if output_name == "rgbd":
        rgb_dir = save_dir / "rgb"
        depth_dir = save_dir / "depth"
        os.makedirs(rgb_dir, exist_ok=True)
        os.makedirs(depth_dir, exist_ok=True)
        output_dirs = {"rgb": rgb_dir, "depth": depth_dir}
        video_path = save_dir / "rgb.mp4"
    else:
        output_dirs = save_dir / output_name
        os.makedirs(output_dirs, exist_ok=True)
        video_path = save_dir / f"{output_name}.mp4"

    writer = None
    if need_video_writer:
        writer = imageio.get_writer(
            video_path,
            fps=video_fps,
            codec="libx264",
            output_params=["-crf", str(video_quality), "-preset", "medium"],
        )
    return output_dirs, writer


def setup_stage_for_phase(
    stage: Usd.Stage,
    render_types: list[str],
    base_mdl_path: str | None = None,
    default_png_path: str | None = None,
) -> None:
    if any(render_type in {"depth", "rgbd"} for render_type in render_types):
        setup_all_prims_cast_shadow_true(stage)
    if "instance" in render_types:
        setup_instance_scene_copy(stage)
    if any(render_type in MATERIAL_OVERRIDE_TYPES for render_type in render_types):
        if base_mdl_path is None or default_png_path is None:
            raise ValueError("base_mdl_path and default_png_path are required for shading renders")
        set_all_material_to_default(stage, base_mdl_path, default_png_path)


def _get_depth_data(camera: Camera, meters_per_unit: float) -> np.ndarray:
    if camera.get_projection_type() == "fisheyeSpherical":
        depth = get_depth_to_camera(camera)
    else:
        depth = camera.get_depth()
    depth[np.isinf(depth)] = 0.0
    return depth * meters_per_unit


def _get_render_data(
    camera: Camera,
    meters_per_unit: float,
    render_type: str,
) -> np.ndarray | dict:
    if render_type in {"rgb", "shading", "shading_randlight"}:
        return camera.get_rgb()
    if render_type == "rgbd":
        return {
            "rgb": camera.get_rgb(),
            "depth": _get_depth_data(camera, meters_per_unit),
        }
    if render_type == "depth":
        return _get_depth_data(camera, meters_per_unit)
    if render_type == "instance":
        return get_src(camera, "seg")
    raise ValueError(f"Unsupported render type: {render_type}")


def _save_render_data(
    render_data: np.ndarray | dict,
    save_dir: Path | dict[str, Path],
    video_writer: Any | None,
    render_type: str,
    frame_index: int,
) -> None:
    if render_type in {"rgb", "shading", "shading_randlight"}:
        cv2.imwrite(
            os.path.join(save_dir, f"{frame_index}.jpg"),
            cv2.cvtColor(render_data, cv2.COLOR_BGR2RGB),
        )
        if video_writer:
            video_writer.append_data(render_data)
    elif render_type == "rgbd":
        rgb, depth = render_data["rgb"], render_data["depth"]
        cv2.imwrite(
            os.path.join(save_dir["rgb"], f"{frame_index}.jpg"),
            cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB),
        )
        np.save(os.path.join(save_dir["depth"], f"{frame_index}.npy"), depth.astype(np.float16))
        if video_writer:
            video_writer.append_data(rgb)
    elif render_type == "depth":
        np.save(os.path.join(save_dir, f"{frame_index}.npy"), render_data.astype(np.float16))
    elif render_type == "instance":
        with open(os.path.join(save_dir, f"{frame_index}_seg.pkl"), "wb") as f:
            pickle.dump(render_data, f)
        if video_writer:
            video_writer.append_data(colorize_instances(render_data["mask"]))


def render_trajectory_any(
    scene_world: World,
    meters_per_unit: float,
    camera: Camera,
    camera_poses: list,
    save_dir: str | Path,
    save_intrinsic: bool = True,
    render_type: str = "rgb",
    output_name: str | None = None,
    save_video: bool = True,
    video_fps: int = 10,
    video_quality: int = 28,
    warmup_frames: int = 8,
) -> None:
    if render_type not in SUPPORT_RENDER_TYPES:
        raise ValueError(f"Unsupported render type: {render_type}")

    save_dir = Path(save_dir)
    output_name = output_name or render_type
    need_video = save_video and render_type in {"rgb", "rgbd", "shading", "shading_randlight"}
    render_save_dir, video_writer = _setup_save_env(
        save_dir,
        output_name,
        need_video,
        video_fps,
        video_quality,
    )

    if warmup_frames > 0 and camera_poses:
        first_position, first_rotation = _process_camera_pose(camera_poses[0], meters_per_unit)
        camera.set_world_pose(first_position, first_rotation)
        for _ in range(warmup_frames * 8):
            scene_world.step()

    for frame_index, camera_pose in enumerate(tqdm(camera_poses, desc=f"Rendering {output_name}")):
        camera_position, camera_rotation = _process_camera_pose(camera_pose, meters_per_unit)
        camera.set_world_pose(camera_position, camera_rotation)
        for _ in range(8):
            scene_world.step()
        render_data = _get_render_data(camera, meters_per_unit, render_type)
        _save_render_data(render_data, render_save_dir, video_writer, render_type, frame_index)

    if video_writer:
        video_writer.close()
    if save_intrinsic:
        intrinsic_name = "camera_intrinsic.json" if render_type == "rgbd" else f"camera_intrinsic_{output_name}.json"
        with open(save_dir / intrinsic_name, "w") as f:
            json.dump(get_intrinsic_matrix(camera).tolist(), f, indent=2)
