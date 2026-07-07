# InternScenes_Gen

[![English](https://img.shields.io/badge/lang-English-blue.svg)](./README.md)
[![中文](https://img.shields.io/badge/lang-Chinese-red.svg)](./README_zh-CN.md)

`InternScenes_Gen` provides the generated-scene subset of InternScenes. This folder includes a lightweight scene composition script, `compose_scene.py`, for reconstructing GLB scenes from released layout files and asset files.

## Directory Structure

After downloading the released data, the expected structure is:

```text
InternScenes_Gen/
  Asset_Library/
    IM/<FactoryName>/<asset_id>/whole.glb
    Infinigen_asset/<room_type>/<room_id>/<asset_name>/whole.glb
  Layout_info/
    <room_type>/<room_id>/layout.json
    <room_type>/<room_id>/StructureMesh/StructureMesh.glb
  total_scene_ids.json
  compose_scene.py
```

Each `layout.json` stores object instances with `model_uid` and `bbox`. The script loads the corresponding `whole.glb` assets from `Asset_Library`, applies the layout transforms, optionally adds the room structure mesh, and exports a composed GLB scene.

## Requirements

```bash
pip install numpy trimesh
```

If you want to keep material and texture information, make sure the downloaded `whole.glb` files contain the corresponding visual assets.

## Compose One Scene

Run from this folder:

```bash
python compose_scene.py --room-id bathroom/0
```

By default, the output is saved to:

```text
InternScenes_Gen/composed_scenes/bathroom_0.glb
```

You can also specify paths explicitly:

```bash
python compose_scene.py --data-root /path/to/InternScenes_Gen --room-id bathroom/0 --output-path /path/to/output/bathroom_0.glb
```

## Compose All Scenes

`total_scene_ids.json` contains all released generated-scene ids. To compose all scenes:

```bash
python compose_scene.py --all --workers 8
```

To use a custom scene-id list:

```bash
python compose_scene.py --room-ids-file /path/to/scene_ids.json --output-dir /path/to/composed_scenes
```

The scene-id file should be a JSON list of strings, for example:

```json
[
  "bathroom/0",
  "bedroom/10000"
]
```

## Useful Options

```text
--data-root        Path to the InternScenes_Gen directory.
--room-id          Compose one scene id. Can be passed multiple times.
--room-ids-file    JSON file containing a list of scene ids.
--all              Compose all scenes in total_scene_ids.json.
--output-dir       Output directory for composed GLB files.
--output-path      Output path for a single composed scene.
--workers          Number of worker threads for loading assets.
--no-texture       Remove texture visuals in the exported GLB.
--no-structure     Do not add StructureMesh/StructureMesh.glb.
```

## Notes

- `IM/...` assets are canonicalized, scaled, rotated, and translated according to the layout bbox.
- `Infinigen_asset/...` assets are expected to be pre-exported in scene coordinates.
- The final composed scene follows the released Y-up GLB convention.
- The script preserves multi-part GLB assets by keeping their internal scene graph transforms.
