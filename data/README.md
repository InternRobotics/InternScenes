[English](README.md) | [中文](README_CN.md)

# Prepare InternScenes-Real2Sim Data

## Data Download

We currently host the dataset on [Hugging Face](https://huggingface.co/datasets/InternRobotics/InternScenes). The released 3D assets are provided in GLB format.

For access to original upstream formats, such as URDF files from PartNet-Mobility, download the raw data from the official sources:

1. Download the Objaverse data [HERE](https://objaverse.allenai.org/).
2. Download the HSSD data [HERE](https://huggingface.co/datasets/hssd/hssd-models).
3. Download the 3D-FUTURE data [HERE](https://tianchi.aliyun.com/specials/promotion/alibaba-3d-future).
4. Download the PartNet-Mobility data [HERE](https://sapien.ucsd.edu/browse).

## Directory Layout

Organize the Real2Sim layout data and GLB asset library under the repository as below.

```text
data/
  asset_library/                 # GLB assets used by scene composition
    objaverse/
    objaverse_old/
    hssd-models/
    3D-FUTURE-model/
    gr100/
    partnet_mobility/
    gen_assets/
  Layout_info/
    {dataset}/
      {scan_id}/
        StructureMesh/           # 3D mesh of the floor and walls
          wall.glb
        layout.json              # Scene layout annotations
```

`layout.json` stores object annotations for one scene. The layout format is listed as follows:

```json
[
  {
    "id": 1,
    "category": "chair",
    "model_uid": "partnet_mobility/39551",
    "bbox": [
      1.041122286614026,
      -1.2630096162069782,
      0.37856578639578786,
      0.42791932981359787,
      0.4573552539873118,
      0.7564487395312743,
      1.384006110201953,
      0.0,
      -0.0
    ]
  }
]
```

`model_uid` is resolved relative to `data/asset_library/`. For example, `partnet_mobility/39551` points to the corresponding PartNet-Mobility asset folder in the local asset library.

# Trajectory and Rendering Data

Trajectory generation and rendering use the data organization documented in [`trajectory_tools/README.md`](../trajectory_tools/README.md). The default layout is:

```text
data/
  source/
    {dataset}/
      part{part}/
        {usd}_usd/
          {scene_name}/
            scene.usd            # The only direct USD file in the scene directory
  env/
    default_no_specular.mdl
    WhiteMode.mdl
    default.png
output/
  camera_poses/                  # Generated trajectory JSON files
  scene_cache/                   # Parsed scene point-cloud caches
  render/                        # Rendered RGB, depth, instance, and shading outputs
```

Each scene directory under `data/source` must contain exactly one direct `.usd` file. If a scene directory contains zero or multiple USD files, trajectory generation and rendering skip that scene instead of choosing one automatically.

For generation commands, rendering commands, output formats, and configuration details, refer to the [trajectory tools guide](../trajectory_tools/README.md).
