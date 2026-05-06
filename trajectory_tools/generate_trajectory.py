"""Generate camera trajectories for USD scenes."""

from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import open3d as o3d
from pxr import Usd

from utils.pcd_utils.filter_scene_noise import classify_prims_by_bbox
from utils.pcd_utils.parse_scene_floor import (
    _extract_floor_metadata,
    extract_floor_heights,
    fix_floor_height_from_metadata,
)
from utils.shortlist_utils import load_shortlist_scenes
from utils.trajectory_utils import (
    PostProcessConfig,
    SceneMap,
    TrajectoryPostProcessor,
    create_strategy,
    load_config,
)
from utils.usd_utils.converters import usd2pcd
from utils.usd_utils.stage_utils import get_all_mesh_prims

DEFAULT_SCENE_DIR = "data/source"
DEFAULT_OUTPUT_DIR = "output/camera_poses"
DEFAULT_CACHE_DIR = "output/scene_cache"


@dataclass
class SceneData:
    scene_pcd: o3d.geometry.PointCloud
    floor_heights: list
    corrected_floor_heights: list
    valid_prims: list
    noise_prims: list
    prim_survival: dict


@dataclass
class FloorResult:
    success_count: int = 0
    attempted_count: int = 0
    failure_reasons: list[str] = field(default_factory=list)


def _load_existing_report(report_path: str) -> dict:
    if os.path.exists(report_path):
        with open(report_path) as f:
            return json.load(f)
    return {}


def _save_report(report_path: str, report: dict) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    tmp = report_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    os.replace(tmp, report_path)


def _find_usd_file(scene_path: str) -> tuple[str | None, int]:
    usd_files = [
        str(path)
        for path in Path(scene_path).glob("*.usd")
        if "copy.usd" not in path.name
    ]
    if len(usd_files) == 1:
        return usd_files[0], 1
    return None, len(usd_files)


def _parse_scene(usd_path: str) -> SceneData | None:
    stage = Usd.Stage.Open(usd_path)
    if stage is None:
        raise RuntimeError(f"Failed to open USD stage: {usd_path}")

    meters_per_unit = stage.GetMetadata("metersPerUnit") or 1.0
    mesh_prims = get_all_mesh_prims(stage)
    if not mesh_prims:
        return None

    prim_survival = classify_prims_by_bbox(mesh_prims, meters_per_unit)
    threshold = 0.1
    valid_prim_paths = {path for path, score in prim_survival.items() if score >= threshold}
    valid_prims = [path for path, score in prim_survival.items() if score >= threshold]
    noise_prims = [path for path, score in prim_survival.items() if score < threshold]
    print(f"[TrajectoryGen] Prim filter: {len(valid_prims)} valid, {len(noise_prims)} noise")

    prim_metadata = _extract_floor_metadata(mesh_prims, meters_per_unit)
    raw = usd2pcd(stage, valid_prim_paths=valid_prim_paths)

    del stage, mesh_prims
    gc.collect()

    scene_pcd = raw.pcd.voxel_down_sample(0.05)
    del raw
    scene_pcd.colors = o3d.utility.Vector3dVector(
        np.ones((len(scene_pcd.points), 3)) * 0.4,
    )

    floor_heights = extract_floor_heights(np.array(scene_pcd.points))
    corrected_floor_heights = [
        fix_floor_height_from_metadata(floor_range[0], prim_metadata)
        for floor_range in floor_heights
    ]

    return SceneData(
        scene_pcd=scene_pcd,
        floor_heights=floor_heights,
        corrected_floor_heights=corrected_floor_heights,
        valid_prims=valid_prims,
        noise_prims=noise_prims,
        prim_survival=prim_survival,
    )


def _save_scene_cache(scene_data: SceneData, cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    ply_path = os.path.join(cache_dir, "scene_pcd.ply")
    json_path = os.path.join(cache_dir, "scene_metadata.json")
    tmp_path = json_path + ".tmp"

    o3d.io.write_point_cloud(ply_path, scene_data.scene_pcd)
    metadata = {
        "floor_heights": scene_data.floor_heights,
        "corrected_floor_heights": scene_data.corrected_floor_heights,
        "valid_prims": scene_data.valid_prims,
        "noise_prims": scene_data.noise_prims,
        "prim_survival": scene_data.prim_survival,
    }
    with open(tmp_path, "w") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, json_path)


def _load_scene_cache(cache_dir: str) -> SceneData | None:
    ply_path = os.path.join(cache_dir, "scene_pcd.ply")
    json_path = os.path.join(cache_dir, "scene_metadata.json")
    if not (os.path.exists(ply_path) and os.path.exists(json_path)):
        return None

    scene_pcd = o3d.io.read_point_cloud(ply_path)
    if len(scene_pcd.points) == 0:
        return None

    with open(json_path) as f:
        meta = json.load(f)
    return SceneData(
        scene_pcd=scene_pcd,
        floor_heights=meta["floor_heights"],
        corrected_floor_heights=meta["corrected_floor_heights"],
        valid_prims=meta["valid_prims"],
        noise_prims=meta["noise_prims"],
        prim_survival=meta["prim_survival"],
    )


def _generate_trajectories_for_floor(
    floor_idx: int,
    floor_height: float,
    scene_data: SceneData,
    cfg,
    output_dir: str,
) -> FloorResult:
    result = FloorResult()
    scene_map = SceneMap(cfg.scene_map)
    try:
        scene_map.build(floor_height, 0.5, scene_data.scene_pcd)
    except Exception as exc:
        result.failure_reasons.append(f"floor {floor_idx}: SceneMap.build failed: {exc}")
        return result

    if len(scene_map.navigable_clusters) == 0:
        result.failure_reasons.append(f"floor {floor_idx}: no navigable clusters")
        return result

    strategy = create_strategy(cfg.strategy.name, cfg.strategy.params)
    sample_count = cfg.camera.sample_number or len(scene_map.navigable_clusters)

    post_cfg = PostProcessConfig(
        min_step_distance=cfg.postprocess.min_step_distance,
        min_step_angle=cfg.postprocess.min_step_angle,
        min_turn_distance=cfg.postprocess.min_turn_distance,
        pitch_rad=cfg.camera.resolve_pitch_rad(),
        camera_height=cfg.camera.resolve_height(),
        bspline_degree=cfg.postprocess.bspline_degree,
        bspline_step=cfg.postprocess.bspline_step,
    )
    post_processor = TrajectoryPostProcessor(post_cfg)

    print(f"[TrajectoryGen] floor {floor_idx}: sampling {sample_count} trajectory(ies)")
    os.makedirs(output_dir, exist_ok=True)

    for traj_idx in range(sample_count):
        result.attempted_count += 1
        ok, generated = strategy.generate(scene_map)
        if not ok:
            result.failure_reasons.append(
                f"f{floor_idx}_t{traj_idx}: {generated.failure_reason or 'unknown'}"
            )
            continue

        processed, reason = post_processor.process(
            generated.waypoints,
            floor_height,
            mode=generated.metadata.get("postprocess_mode", "standard"),
        )
        if processed is None:
            result.failure_reasons.append(f"f{floor_idx}_t{traj_idx} postprocess: {reason}")
            continue

        path = os.path.join(output_dir, f"f{floor_idx}_t{traj_idx}.json")
        with open(path, "w") as f:
            json.dump(processed.camera_poses, f, indent=2)
        result.success_count += 1

    print(f"[TrajectoryGen] floor {floor_idx}: {result.success_count}/{sample_count} succeeded")
    return result


def _build_scene_report_entry(floor_heights: list, floor_results: list[FloorResult], scene_data: SceneData) -> dict:
    total_success = sum(result.success_count for result in floor_results)
    total_attempted = sum(result.attempted_count for result in floor_results)
    failure_reasons = []
    for result in floor_results:
        failure_reasons.extend(result.failure_reasons)

    if total_success == 0 and total_attempted > 0:
        status = "failed"
    elif total_success < total_attempted:
        status = "partial"
    elif total_success > 0:
        status = "success"
    else:
        status = "skipped"

    return {
        "status": status,
        "floors_detected": len(floor_heights),
        "trajectories_generated": total_success,
        "trajectories_attempted": total_attempted,
        "failure_reasons": failure_reasons,
        "prim_filter": {
            "valid_count": len(scene_data.valid_prims),
            "noise_count": len(scene_data.noise_prims),
            "noise_prims": scene_data.noise_prims,
            "survival_rates": scene_data.prim_survival,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate camera trajectories for USD scenes.")
    parser.add_argument("--config", required=True, help="YAML trajectory config path.")
    parser.add_argument("--dataset", default="GRScenes", help="Dataset name under --scene-dir.")
    parser.add_argument("--part", type=int, default=1, help="Dataset part index.")
    parser.add_argument("--usd", type=int, required=True, help="USD folder id, e.g. 101 for 101_usd.")
    parser.add_argument("--specific", default=None, help="Optional single scene name inside the USD folder.")
    parser.add_argument("--shortlist", default=None, help="Optional scene_shortlist.csv.")
    parser.add_argument("--min-rating", type=int, default=3, help="Minimum rating used with --shortlist.")
    parser.add_argument("--scene-dir", default=DEFAULT_SCENE_DIR, help="Root scene directory.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Root trajectory output directory.")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="Root parsed-scene cache directory.")
    parser.add_argument("--override", nargs="*", default=[], help="Dotted YAML overrides, e.g. camera.sample_number=5.")
    parser.add_argument("--retry-failed", action="store_true", help="Regenerate scenes marked failed in the report.")
    parser.add_argument("--force-reparse", action="store_true", help="Ignore cached scene point clouds.")
    return parser.parse_args()


def _parse_overrides(raw: list[str]) -> dict:
    overrides = {}
    for item in raw:
        key, value = item.split("=", 1)
        try:
            value = float(value) if "." in value else int(value)
        except ValueError:
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
        overrides[key] = value
    return overrides


def _resolve_scenes(args: argparse.Namespace, usd_folder: str) -> list[str]:
    if args.specific:
        return [args.specific]
    if args.shortlist:
        return load_shortlist_scenes(args.shortlist, args.usd, args.min_rating)
    return sorted(
        name for name in os.listdir(usd_folder)
        if os.path.isdir(os.path.join(usd_folder, name))
    )


def process_usd_folder(args: argparse.Namespace, cfg) -> None:
    rel_usd = f"part{args.part}/{args.usd}_usd"
    scene_root = os.path.join(args.scene_dir, args.dataset)
    usd_folder = os.path.join(scene_root, rel_usd)
    if not os.path.isdir(usd_folder):
        raise FileNotFoundError(f"USD folder not found: {usd_folder}")

    output_root = os.path.join(args.output_dir, args.dataset)
    cache_root = os.path.join(args.cache_dir, args.dataset)
    scenes = _resolve_scenes(args, usd_folder)
    print(f"[TrajectoryGen] usd={args.usd}, strategy={cfg.strategy.name}, scenes={len(scenes)}")

    report_dir = os.path.join(output_root, rel_usd)
    report_path = os.path.join(report_dir, f"generation_report_{cfg.strategy.name}.json")
    report = _load_existing_report(report_path)

    for scene_name in scenes:
        scene_output = os.path.join(output_root, rel_usd, scene_name)
        traj_dir = os.path.join(scene_output, cfg.strategy.name)

        if scene_name in report:
            status = report[scene_name].get("status")
            if status == "failed" and args.retry_failed:
                if os.path.exists(traj_dir):
                    shutil.rmtree(traj_dir)
            else:
                print(f"[TrajectoryGen] {scene_name}: already processed ({status}), skip")
                continue

        scene_path = os.path.join(usd_folder, scene_name)
        usd_path, found_count = _find_usd_file(scene_path)
        if usd_path is None:
            report[scene_name] = {"status": "skipped", "reason": f"expected 1 USD, found {found_count}"}
            _save_report(report_path, report)
            continue

        cache_dir = os.path.join(cache_root, rel_usd, scene_name)
        scene_data = None if args.force_reparse else _load_scene_cache(cache_dir)
        if scene_data is None:
            try:
                scene_data = _parse_scene(usd_path)
            except Exception as exc:
                report[scene_name] = {"status": "skipped", "reason": f"parse failed: {exc}"}
                _save_report(report_path, report)
                continue
            if scene_data is not None:
                _save_scene_cache(scene_data, cache_dir)

        if scene_data is None:
            report[scene_name] = {"status": "skipped", "reason": "no mesh geometry in USD"}
            _save_report(report_path, report)
            continue

        if len(scene_data.floor_heights) == 0:
            report[scene_name] = {"status": "skipped", "reason": "no floors detected"}
            _save_report(report_path, report)
            continue

        floor_results = [
            _generate_trajectories_for_floor(
                floor_idx,
                floor_height,
                scene_data,
                cfg,
                traj_dir,
            )
            for floor_idx, floor_height in enumerate(scene_data.corrected_floor_heights)
        ]
        report[scene_name] = _build_scene_report_entry(
            scene_data.floor_heights,
            floor_results,
            scene_data,
        )

        total_success = sum(result.success_count for result in floor_results)
        if total_success == 0 and os.path.exists(traj_dir):
            shutil.rmtree(traj_dir)
        _save_report(report_path, report)

    print(f"[TrajectoryGen] Report saved: {report_path}")


def main() -> None:
    args = parse_args()
    overrides = _parse_overrides(args.override) if args.override else None
    cfg = load_config(args.config, overrides)
    process_usd_folder(args, cfg)


if __name__ == "__main__":
    main()
