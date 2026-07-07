#!/usr/bin/env python3
"""Compose InternScenes_Gen layouts into GLB scenes.

Expected dataset layout:

    InternScenes_Gen/
      Asset_Library/
        IM/<FactoryName>/<asset_id>/whole.glb
        Infinigen_asset/<room_type>/<room_id>/<asset_name>/whole.glb
      Layout_info/
        <room_type>/<room_id>/layout.json
        <room_type>/<room_id>/StructureMesh/StructureMesh.glb
      total_scene_ids.json
      compose_scene.py

Examples:

    python compose_scene.py --room-id bathroom/0
    python compose_scene.py --room-id bathroom/0 --output-path bathroom_0.glb
    python compose_scene.py --all --workers 8
    python compose_scene.py --data-root /path/to/InternScenes_Gen --all
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import warnings

import numpy as np
import trimesh


# Factory asset canonicalization:
# first axis is the asset's front direction, second axis is its up direction.
# Canonical scene convention after correction: front is +X and up is +Z.
FACTORY_ORIENTATIONS: Dict[str, Tuple[str, str]] = {
    "BarChairFactory": ("Z", "Y"),
    "BeverageFridgeFactory": ("X", "Y"),
    "BottleFactory": ("Z", "Y"),
    "DishwasherFactory": ("X", "Y"),
    "HardwareFactory": ("Y", "Z"),
    "KitchenCabinetFactory": ("X", "Y"),
    "LampFactory": ("Z", "Y"),
    "LidFactory": ("Z", "Y"),
    "LiteDoorFactory": ("Z", "Y"),
    "MicrowaveFactory": ("X", "Y"),
    "OfficeChairFactory": ("Z", "Y"),
    "OvenFactory": ("X", "Y"),
    "PanFactory": ("X", "Y"),
    "PlateOnRackBaseFactory": ("Z", "Y"),
    "PotFactory": ("Z", "Y"),
    "RackFactory": ("Z", "Y"),
    "TVFactory": ("Z", "Y"),
    "TableCocktailFactory": ("X", "Y"),
    "TableDiningFactory": ("Z", "Y"),
    "TapFactory": ("-X", "Y"),
    "ToiletFactory": ("Z", "Y"),
    "VaseFactory": ("Z", "Y"),
    "WindowFactory": ("Y", "Z"),
}


def parse_axis(axis: str) -> Tuple[int, float]:
    """Return axis index and sign for strings like X, -Y, or Z."""
    if axis.startswith("-"):
        return {"X": 0, "Y": 1, "Z": 2}[axis[1:]], -1.0
    return {"X": 0, "Y": 1, "Z": 2}[axis], 1.0


def axis_vector(axis: str) -> np.ndarray:
    index, sign = parse_axis(axis)
    vector = np.zeros(3)
    vector[index] = sign
    return vector


def get_transform_from_factory(factory_name: str) -> np.ndarray:
    """Return the rotation that maps a factory asset to canonical pose."""
    if factory_name not in FACTORY_ORIENTATIONS:
        raise ValueError(f"Unknown factory orientation: {factory_name}")

    source_front, source_up = FACTORY_ORIENTATIONS[factory_name]
    source_front_vec = axis_vector(source_front)
    source_up_vec = axis_vector(source_up)
    source_side_vec = np.cross(source_front_vec, source_up_vec)
    source_basis = np.column_stack((source_front_vec, source_up_vec, source_side_vec))

    target_front_vec = np.array([1.0, 0.0, 0.0])
    target_up_vec = np.array([0.0, 0.0, 1.0])
    target_side_vec = np.cross(target_front_vec, target_up_vec)
    target_basis = np.column_stack((target_front_vec, target_up_vec, target_side_vec))

    transform = np.eye(4)
    transform[:3, :3] = target_basis @ source_basis.T
    return transform


def load_glb(path: Path, use_texture: bool = True) -> trimesh.Trimesh | trimesh.Scene:
    """Load a GLB as either a Trimesh or Scene.

    We intentionally do not force mesh loading because many GLB assets contain
    multiple parts with local transforms that should be preserved.
    """
    if not path.exists():
        raise FileNotFoundError(f"GLB file not found: {path}")

    loaded = trimesh.load(str(path))
    if not use_texture:
        clear_texture(loaded)
    return loaded


def clear_texture(mesh_or_scene: trimesh.Trimesh | trimesh.Scene) -> None:
    """Remove texture visuals from a mesh or every geometry in a scene."""
    from trimesh.visual.texture import TextureVisuals

    empty_visual = TextureVisuals()
    if isinstance(mesh_or_scene, trimesh.Scene):
        for geometry in mesh_or_scene.geometry.values():
            geometry.visual = empty_visual
    else:
        mesh_or_scene.visual = empty_visual


def add_mesh_or_scene(
    target_scene: trimesh.Scene,
    mesh_or_scene: trimesh.Trimesh | trimesh.Scene,
    parent_node_name: str,
    parent_transform: np.ndarray,
) -> None:
    """Add a mesh or all geometries from a sub-scene under one parent node."""
    target_scene.graph.update(frame_to=parent_node_name, matrix=parent_transform)

    if isinstance(mesh_or_scene, trimesh.Scene):
        for geometry_name, geometry in mesh_or_scene.geometry.items():
            node_names = mesh_or_scene.graph.geometry_nodes.get(geometry_name, [])
            if not node_names:
                target_scene.add_geometry(
                    geometry.copy(),
                    geom_name=f"{parent_node_name}_{geometry_name}",
                    parent_node_name=parent_node_name,
                )
                continue

            for index, node_name in enumerate(node_names):
                internal_transform, _ = mesh_or_scene.graph.get(node_name)
                target_scene.add_geometry(
                    geometry.copy(),
                    geom_name=f"{parent_node_name}_{index}_{geometry_name}",
                    transform=internal_transform,
                    parent_node_name=parent_node_name,
                )
    else:
        target_scene.add_geometry(
            mesh_or_scene.copy(),
            geom_name=f"{parent_node_name}_geom",
            parent_node_name=parent_node_name,
        )


def transform_for_bbox(bbox: Sequence[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split a layout bbox into position, size, and ZXY Euler rotation."""
    if len(bbox) != 9:
        raise ValueError(f"bbox must have 9 numbers, got {len(bbox)}")
    position = np.array(bbox[0:3], dtype=np.float64)
    size = np.array(bbox[3:6], dtype=np.float64)
    rotation = np.array(bbox[6:9], dtype=np.float64)
    return position, size, rotation


def process_object(
    object_info: Dict[str, Any],
    asset_library_dir: Path,
    use_texture: bool,
) -> Optional[Tuple[trimesh.Trimesh | trimesh.Scene, str, np.ndarray]]:
    """Load one object asset and return it with its scene transform."""
    model_uid = object_info.get("model_uid", "")
    if not model_uid:
        warnings.warn(f"Skipping object with empty model_uid: {object_info}")
        return None

    object_id = object_info.get("id", "unknown")
    asset_path = asset_library_dir / model_uid / "whole.glb"
    mesh_or_scene = load_glb(asset_path, use_texture=use_texture)

    if model_uid.startswith("IM/"):
        transform = np.eye(4)
        parts = model_uid.split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid IM model_uid: {model_uid}")

        factory_name = parts[1]
        try:
            correction = get_transform_from_factory(factory_name)
            mesh_or_scene.apply_translation(-mesh_or_scene.bounding_box.centroid)
            mesh_or_scene.apply_transform(correction)
        except ValueError as exc:
            warnings.warn(f"{exc}; composing without factory correction")

        position, target_size, rotation = transform_for_bbox(object_info["bbox"])
        mesh_extents = np.maximum(mesh_or_scene.bounding_box.extents, 1e-6)
        scale = target_size / mesh_extents

        scale_matrix = np.diag([scale[0], scale[1], scale[2], 1.0])
        transform = scale_matrix @ transform

        rotation_matrix = trimesh.transformations.euler_matrix(
            rotation[0], rotation[1], rotation[2], axes="rzxy"
        )
        transform = rotation_matrix @ transform

        translation_matrix = np.eye(4)
        translation_matrix[:3, 3] = position
        transform = translation_matrix @ transform

        # Convert the final composed scene to the released Y-up convention.
        scene_rotation = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
        transform = scene_rotation @ transform

    elif model_uid.startswith("Infinigen_asset/"):
        # These assets are exported in scene coordinates during preprocessing.
        transform = np.eye(4)
    else:
        raise ValueError(
            f"Unsupported model_uid prefix for {model_uid!r}. "
            "Expected 'IM/' or 'Infinigen_asset/'."
        )

    parent_node_name = f"{object_id}_{model_uid}".replace(os.sep, "_")
    return mesh_or_scene, parent_node_name, transform


def compose_scene(
    room_id: str,
    data_root: Path,
    output_path: Optional[Path] = None,
    use_texture: bool = True,
    add_structure: bool = True,
    workers: int = 8,
) -> Path:
    """Compose one InternScenes_Gen room into a GLB file."""
    layout_dir = data_root / "Layout_info" / room_id
    asset_library_dir = data_root / "Asset_Library"
    layout_path = layout_dir / "layout.json"

    if not layout_path.exists():
        raise FileNotFoundError(f"layout.json not found: {layout_path}")
    if not asset_library_dir.exists():
        raise FileNotFoundError(f"Asset_Library not found: {asset_library_dir}")

    if output_path is None:
        output_dir = data_root / "composed_scenes"
        output_path = output_dir / f"{room_id.replace('/', '_')}.glb"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with layout_path.open("r", encoding="utf-8") as file:
        scene_objects = json.load(file)

    scene = trimesh.Scene()
    workers = max(1, workers)

    if workers == 1:
        results = [
            process_object(object_info, asset_library_dir, use_texture)
            for object_info in scene_objects
        ]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(process_object, object_info, asset_library_dir, use_texture)
                for object_info in scene_objects
            ]
            for future in as_completed(futures):
                results.append(future.result())

    composed_objects = 0
    for result in results:
        if result is None:
            continue
        mesh_or_scene, parent_node_name, transform = result
        add_mesh_or_scene(scene, mesh_or_scene, parent_node_name, transform)
        composed_objects += 1

    if add_structure:
        structure_path = layout_dir / "StructureMesh" / "StructureMesh.glb"
        if structure_path.exists():
            structure = load_glb(structure_path, use_texture=use_texture)
            add_mesh_or_scene(scene, structure, "Structure_Mesh", np.eye(4))
        else:
            warnings.warn(f"StructureMesh.glb not found, skipping: {structure_path}")

    if not use_texture:
        clear_texture(scene)

    scene.export(str(output_path))
    print(
        f"Saved {output_path} "
        f"(objects: {composed_objects}/{len(scene_objects)}, structure: {add_structure})"
    )
    return output_path


def load_room_ids(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as file:
        room_ids = json.load(file)
    if not isinstance(room_ids, list) or not all(isinstance(item, str) for item in room_ids):
        raise ValueError(f"Room id file must be a JSON list of strings: {path}")
    return room_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compose InternScenes_Gen layout and assets into GLB scenes."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Path to the InternScenes_Gen directory.",
    )
    parser.add_argument(
        "--room-id",
        action="append",
        default=[],
        help="Room id such as bathroom/0. Can be passed multiple times.",
    )
    parser.add_argument(
        "--room-ids-file",
        type=Path,
        default=None,
        help="JSON file containing a list of room ids. Defaults to total_scene_ids.json for --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Compose all room ids listed in total_scene_ids.json or --room-ids-file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for composed GLBs. Defaults to <data-root>/composed_scenes.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Output GLB path. Only valid when composing exactly one room.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(8, os.cpu_count() or 1),
        help="Number of threads used to load object assets.",
    )
    parser.add_argument(
        "--no-texture",
        action="store_true",
        help="Drop texture visuals from the exported GLB.",
    )
    parser.add_argument(
        "--no-structure",
        action="store_true",
        help="Do not add StructureMesh/StructureMesh.glb.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()

    room_ids: List[str] = list(args.room_id)
    if args.all:
        room_ids_file = args.room_ids_file or data_root / "total_scene_ids.json"
        room_ids.extend(load_room_ids(room_ids_file))
    elif args.room_ids_file is not None:
        room_ids.extend(load_room_ids(args.room_ids_file))

    # Preserve order while removing duplicates.
    room_ids = list(dict.fromkeys(room_ids))

    if not room_ids:
        raise ValueError("No room ids provided. Use --room-id, --room-ids-file, or --all.")
    if args.output_path is not None and len(room_ids) != 1:
        raise ValueError("--output-path can only be used when composing one room.")

    for room_id in room_ids:
        if args.output_path is not None:
            output_path = args.output_path
        else:
            output_dir = args.output_dir or data_root / "composed_scenes"
            output_path = output_dir / f"{room_id.replace('/', '_')}.glb"

        compose_scene(
            room_id=room_id,
            data_root=data_root,
            output_path=output_path,
            use_texture=not args.no_texture,
            add_structure=not args.no_structure,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()
