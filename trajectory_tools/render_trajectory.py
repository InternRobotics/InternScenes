"""Render generated camera trajectories in Isaac Sim."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from natsort import natsorted

from utils.usd_utils.path_utils import find_single_usd

LAUNCHER_SETTINGS = {
    "headless": True,
    "anti_aliasing": 4,
    "multi_gpu": False,
    "renderer": "RayTracedLighting",
    "samples_per_pixel_per_frame": 1024,
    "max_bounces": 4,
    "max_volume_bounces": 1,
    "max_specular_transmission_bounces": 4,
}

DEFAULT_MDL_PATH = "data/env/default_no_specular.mdl"
WHITE_MDL_PATH = "data/env/WhiteMode.mdl"
DEFAULT_PNG_PATH = "data/env/default.png"


@dataclass
class CameraConfig:
    image_width: int
    image_height: int
    focal_length: float
    vertical_aperture: float
    panorama: bool


class TrajectoryRenderer:
    def __init__(
        self,
        scene_asset_dir: str,
        trajectory_dir: str,
        output_dir: str,
        camera_config: CameraConfig,
        render_types: list[str],
        strategy_name: str,
        default_mdl_path: str = DEFAULT_MDL_PATH,
        white_mdl_path: str = WHITE_MDL_PATH,
        default_png_path: str = DEFAULT_PNG_PATH,
        save_video: bool = True,
        light_per_trajectory: bool = False,
        camera_light: bool = False,
    ) -> None:
        self.scene_asset_dir = scene_asset_dir
        self.trajectory_dir = trajectory_dir
        self.output_dir = output_dir
        self.default_mdl_path = default_mdl_path
        self.white_mdl_path = white_mdl_path
        self.default_png_path = default_png_path
        self.render_types = render_types
        self.strategy_name = strategy_name
        self.camera_resolution = (camera_config.image_width, camera_config.image_height)
        self.focal_length = camera_config.focal_length
        self.vertical_aperture = camera_config.vertical_aperture
        self.use_panorama = camera_config.panorama
        self.save_video = save_video
        self.light_per_trajectory = light_per_trajectory
        self.camera_light = camera_light

    def _output_type_name(self, render_type: str) -> str:
        if self.camera_light and render_type in ("rgb", "shading"):
            return f"{render_type}_camlight"
        return render_type

    def _get_trajectory_paths(self, scene_name: str) -> list[str]:
        scene_trajectory_dir = os.path.join(
            self.trajectory_dir,
            scene_name,
            self.strategy_name,
        )
        if not os.path.isdir(scene_trajectory_dir):
            return []
        return natsorted(
            os.path.join(scene_trajectory_dir, name)
            for name in os.listdir(scene_trajectory_dir)
            if name.endswith(".json")
        )

    def _get_scene_asset_path(self, scene_name: str) -> tuple[str | None, list[str]]:
        scene_asset_dir = os.path.join(self.scene_asset_dir, scene_name)
        if not os.path.isdir(scene_asset_dir):
            return None, []
        return find_single_usd(scene_asset_dir)

    def _check_render_complete(
        self,
        render_output_dir: str,
        trajectory_path: str,
        render_type: str,
    ) -> bool:
        output_name = self._output_type_name(render_type)
        with open(trajectory_path) as f:
            camera_poses = json.load(f)
        num_frames = len(camera_poses)

        if render_type == "rgbd":
            rgb_dir = os.path.join(render_output_dir, "rgb")
            depth_dir = os.path.join(render_output_dir, "depth")
            if not (os.path.exists(rgb_dir) and os.path.exists(depth_dir)):
                return False
            rgb_files = [name for name in os.listdir(rgb_dir) if name.endswith(".jpg")]
            depth_files = [name for name in os.listdir(depth_dir) if name.endswith(".npy")]
            if len(rgb_files) < num_frames or len(depth_files) < num_frames:
                return False
            if self.save_video and not os.path.exists(os.path.join(render_output_dir, "rgb.mp4")):
                return False
            return os.path.exists(os.path.join(render_output_dir, "camera_intrinsic.json"))

        output_type_dir = os.path.join(render_output_dir, output_name)
        if not os.path.exists(output_type_dir):
            return False

        ext_by_type = {
            "rgb": ".jpg",
            "depth": ".npy",
            "instance": "_seg.pkl",
            "shading": ".jpg",
            "shading_randlight": ".jpg",
        }
        ext = ext_by_type.get(render_type)
        if ext is None:
            return False
        existing_files = [name for name in os.listdir(output_type_dir) if name.endswith(ext)]
        if len(existing_files) < num_frames:
            return False

        if self.save_video and render_type in {"rgb", "shading", "shading_randlight"}:
            if not os.path.exists(os.path.join(render_output_dir, f"{output_name}.mp4")):
                return False

        if render_type not in MATERIAL_OVERRIDE_TYPES:
            intrinsic_path = os.path.join(render_output_dir, f"camera_intrinsic_{output_name}.json")
            return os.path.exists(intrinsic_path)
        return True

    def _compose_render_settings(self, scene_usd_path: str) -> dict[str, Any]:
        world, stage, meters_per_unit = load_scene_to_world(
            scene_usd_path,
            self.default_mdl_path,
        )
        camera = init_camera(
            image_width=self.camera_resolution[0],
            image_height=self.camera_resolution[1],
        )
        setup_camera(
            camera,
            with_semantic="instance" in self.render_types,
            focal_length=self.focal_length,
            vertical_aperture=self.vertical_aperture,
            panorama=self.use_panorama,
        )
        return {
            "world": world,
            "stage": stage,
            "meters_per_unit": meters_per_unit,
            "camera": camera,
        }

    def _render_single_trajectory(
        self,
        render_setting: dict[str, Any],
        output_dir: str,
        render_types: list[str],
        save_intrinsic: bool = True,
    ) -> None:
        trajectory_path = os.path.join(output_dir, "camera_poses.json")
        with open(trajectory_path) as f:
            camera_poses = json.load(f)

        for render_type in render_types:
            output_name = self._output_type_name(render_type)
            if self._check_render_complete(output_dir, trajectory_path, render_type):
                print(f"[Renderer] Skipping complete output: {output_dir}/{output_name}")
                continue
            render_trajectory_any(
                render_setting["world"],
                render_setting["meters_per_unit"],
                render_setting["camera"],
                camera_poses,
                output_dir,
                render_type=render_type,
                output_name=output_name,
                save_intrinsic=save_intrinsic,
                save_video=self.save_video,
            )

    def render_scene(
        self,
        scene_name: str,
        trajectory_index: int | None = None,
    ) -> None:
        trajectory_paths = self._get_trajectory_paths(scene_name)
        if not trajectory_paths:
            print(f"[Renderer] Skipping {scene_name}: no trajectories for {self.strategy_name}")
            return

        scene_usd_path, usd_files = self._get_scene_asset_path(scene_name)
        if scene_usd_path is None:
            scene_asset_dir = os.path.join(self.scene_asset_dir, scene_name)
            found = ", ".join(os.path.basename(path) for path in usd_files) or "none"
            print(
                f"[Renderer] Skipping {scene_name}: expected exactly 1 USD file "
                f"in {scene_asset_dir}, found {len(usd_files)}: {found}"
            )
            return

        if trajectory_index is not None:
            trajectory_paths = [trajectory_paths[trajectory_index]]

        render_setting = self._compose_render_settings(scene_usd_path)
        standard_types = [name for name in self.render_types if name not in MATERIAL_OVERRIDE_TYPES]
        shading_types = [name for name in self.render_types if name in MATERIAL_OVERRIDE_TYPES]

        output_scene_dir = os.path.join(self.output_dir, scene_name)
        traj_output_dirs = {}
        for trajectory_path in trajectory_paths:
            traj_name = Path(trajectory_path).stem
            output_dir = os.path.join(output_scene_dir, self.strategy_name, traj_name)
            os.makedirs(output_dir, exist_ok=True)
            shutil.copy(trajectory_path, os.path.join(output_dir, "camera_poses.json"))
            traj_output_dirs[trajectory_path] = output_dir

        if standard_types:
            setup_stage_for_phase(render_setting["stage"], standard_types)
            for trajectory_path in trajectory_paths:
                self._render_single_trajectory(
                    render_setting,
                    traj_output_dirs[trajectory_path],
                    standard_types,
                )

        if shading_types:
            setup_stage_for_phase(
                render_setting["stage"],
                shading_types,
                base_mdl_path=self.white_mdl_path,
                default_png_path=self.default_png_path,
            )
            if "shading_randlight" in shading_types and not self.light_per_trajectory:
                light_params = randomize_all_light_attributes(render_setting["stage"])
                light_params_path = os.path.join(output_scene_dir, self.strategy_name, "light_params.json")
                os.makedirs(os.path.dirname(light_params_path), exist_ok=True)
                with open(light_params_path, "w") as f:
                    json.dump(light_params, f, indent=2)

            for trajectory_path in trajectory_paths:
                output_dir = traj_output_dirs[trajectory_path]
                if "shading_randlight" in shading_types and self.light_per_trajectory:
                    light_params = randomize_all_light_attributes(render_setting["stage"])
                    with open(os.path.join(output_dir, "light_params.json"), "w") as f:
                        json.dump(light_params, f, indent=2)
                self._render_single_trajectory(
                    render_setting,
                    output_dir,
                    shading_types,
                    save_intrinsic=False,
                )

    def reset_env(self) -> None:
        delete_prim("/World/scene")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render generated trajectories in Isaac Sim.")
    parser.add_argument("--dataset", default="GRScenes")
    parser.add_argument("--part", type=int, default=1)
    parser.add_argument("--usd", type=int, required=True)
    parser.add_argument("--scene", default=None, help="Optional single scene name.")
    parser.add_argument("--scene-idx", type=int, default=None, help="Optional scene index after sorting.")
    parser.add_argument("--trajectory-index", type=int, default=None, help="Optional trajectory index in each scene.")
    parser.add_argument("--data-dir", default="data/source", help="Root scene directory.")
    parser.add_argument("--trajectory-dir", default="output/camera_poses", help="Root trajectory directory.")
    parser.add_argument("--output-dir", default="output/render", help="Root render output directory.")
    parser.add_argument("--strategy", nargs="+", default=["astar_nav"], help="Strategy names, or 'all'.")
    parser.add_argument("--rgb", action="store_true")
    parser.add_argument("--depth", action="store_true")
    parser.add_argument("--instance", action="store_true")
    parser.add_argument("--shading", action="store_true")
    parser.add_argument("--shading-randlight", action="store_true")
    parser.add_argument("--panorama", action="store_true")
    parser.add_argument("--auto-expose", action="store_true")
    parser.add_argument("--camera-light", action="store_true")
    parser.add_argument("--no-video", action="store_true")
    parser.add_argument("--light-per-trajectory", action="store_true")
    return parser.parse_args()


def _configure_exposure(args: argparse.Namespace) -> None:
    if args.auto_expose:
        omni.kit.commands.execute("ChangeSetting", path="/rtx/post/histogram/enabled", value=True)
        omni.kit.commands.execute("ChangeSetting", path="/rtx/post/histogram/whiteScale", value=10.0)
    else:
        omni.kit.commands.execute("ChangeSetting", path="/rtx/post/tonemap/filmIso", value=80.0)
        omni.kit.commands.execute("ChangeSetting", path="/rtx/post/tonemap/cameraShutter", value=200.0)
        omni.kit.commands.execute("ChangeSetting", path="/rtx/post/tonemap/fNumber", value=10.0)

    if args.camera_light:
        action_registry = omni.kit.actions.core.get_action_registry()
        action = action_registry.get_action(
            "omni.kit.viewport.menubar.lighting",
            "set_lighting_mode_camera",
        )
        action.execute()


def _resolve_render_types(args: argparse.Namespace) -> list[str]:
    render_types = []
    if args.rgb and args.depth:
        render_types.append("rgbd")
    elif args.rgb:
        render_types.append("rgb")
    elif args.depth:
        render_types.append("depth")
    if args.instance:
        render_types.append("instance")
    if args.shading:
        render_types.append("shading")
    if args.shading_randlight:
        render_types.append("shading_randlight")
    return render_types or ["rgbd"]


def _discover_strategies(trajectory_dir: str, usd_str: str) -> list[str]:
    traj_usd_dir = os.path.join(trajectory_dir, usd_str)
    if not os.path.isdir(traj_usd_dir):
        return []
    strategies = set()
    for scene_name in os.listdir(traj_usd_dir):
        scene_dir = os.path.join(traj_usd_dir, scene_name)
        if not os.path.isdir(scene_dir):
            continue
        for name in os.listdir(scene_dir):
            strategy_dir = os.path.join(scene_dir, name)
            if os.path.isdir(strategy_dir) and any(item.endswith(".json") for item in os.listdir(strategy_dir)):
                strategies.add(name)
    return sorted(strategies)


def _resolve_strategies(args: argparse.Namespace, trajectory_dir: str, usd_str: str) -> list[str]:
    if args.strategy == ["all"]:
        return _discover_strategies(trajectory_dir, usd_str)
    return args.strategy


def _resolve_scene_names(
    args: argparse.Namespace,
    data_dir: str,
    trajectory_dir: str,
    usd_str: str,
    strategies: list[str],
) -> list[str]:
    if args.scene is not None:
        return [f"{usd_str}/{args.scene}"]

    usd_dir = os.path.join(data_dir, usd_str)
    traj_dir = os.path.join(trajectory_dir, usd_str)
    scene_names = []
    for scene_name in sorted(set(os.listdir(usd_dir)) & set(os.listdir(traj_dir))):
        if any(os.path.isdir(os.path.join(traj_dir, scene_name, strategy)) for strategy in strategies):
            scene_names.append(f"{usd_str}/{scene_name}")

    scene_names = natsorted(scene_names)
    if args.scene_idx is not None:
        return [scene_names[args.scene_idx]]
    return scene_names


def main() -> None:
    global omni, SimulationApp, delete_prim
    global load_scene_to_world, init_camera, setup_camera
    global render_trajectory_any, setup_stage_for_phase, MATERIAL_OVERRIDE_TYPES
    global randomize_all_light_attributes

    args = parse_args()

    from isaacsim import SimulationApp
    simulation_app = SimulationApp(LAUNCHER_SETTINGS)

    import omni
    from omni.isaac.core.utils.prims import delete_prim

    from utils.common_utils.render_utils import (
        MATERIAL_OVERRIDE_TYPES,
        render_trajectory_any,
        setup_stage_for_phase,
    )
    from utils.common_utils.sim_utils import init_camera, load_scene_to_world, setup_camera
    from utils.usd_utils.prim_utils import randomize_all_light_attributes

    _configure_exposure(args)

    usd_str = f"{args.usd}_usd"
    data_dir = os.path.join(args.data_dir, args.dataset, f"part{args.part}")
    trajectory_dir = os.path.join(args.trajectory_dir, args.dataset, f"part{args.part}")
    output_dir = os.path.join(args.output_dir, args.dataset, f"part{args.part}")

    camera_config = (
        CameraConfig(2048, 1024, 9.5, 27, panorama=True)
        if args.panorama
        else CameraConfig(800, 400, 3.5, 27, panorama=False)
    )
    render_types = _resolve_render_types(args)
    strategies = _resolve_strategies(args, trajectory_dir, usd_str)
    scene_names = _resolve_scene_names(args, data_dir, trajectory_dir, usd_str, strategies)

    print(f"[Renderer] Strategies: {strategies}")
    print(f"[Renderer] Scenes: {len(scene_names)}")
    print(f"[Renderer] Render types: {render_types}")

    for strategy in strategies:
        renderer = TrajectoryRenderer(
            scene_asset_dir=data_dir,
            trajectory_dir=trajectory_dir,
            output_dir=output_dir,
            camera_config=camera_config,
            render_types=render_types,
            strategy_name=strategy,
            save_video=not args.no_video,
            light_per_trajectory=args.light_per_trajectory,
            camera_light=args.camera_light,
        )
        for scene_name in scene_names:
            if not os.path.isdir(os.path.join(trajectory_dir, scene_name, strategy)):
                continue
            print(f"[Renderer] Rendering {scene_name} ({strategy})")
            renderer.render_scene(scene_name, trajectory_index=args.trajectory_index)
            renderer.reset_env()

    simulation_app.close()


if __name__ == "__main__":
    main()
