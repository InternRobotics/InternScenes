[English](README.md) | [中文](README_CN.md)

# Trajectory Tools

`trajectory_tools` provides the release pipeline for InternScenes camera trajectories:

1. Generate camera pose trajectories from USD scene assets.
2. Render RGB, depth, instance segmentation, shading, and randomized-light shading in Isaac Sim.

This document only covers data contracts, configuration, and command usage. Environment setup is documented in the repository-level README files.

## Data Layout

Commands in this document are intended to run from the repository root. Default paths are resolved relative to the current working directory.

```text
data/
  source/
    GRScenes/
      part1/
        101_usd/
          scene_00001/
            scene.usd          # the only USD file in the scene directory
  env/
    default_no_specular.mdl
    WhiteMode.mdl
    default.png
output/
  camera_poses/
  scene_cache/
  render/
```

Each scene directory must contain exactly one direct `.usd` file. Both trajectory generation and rendering load that file. If a scene directory contains zero or multiple USD files, the scene is skipped instead of selecting an arbitrary asset.

`data/env` contains material resources used by rendering and material-reference repair.

## Generate Trajectories

Generate trajectories for every scene under `data/source/{dataset}/part{part}/{usd}_usd/`:

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101
```

Process a single scene:

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --specific scene_00001
```

Use the straight-line forward-motion strategy:

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/forward_motion.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101
```

Override scalar YAML values from the command line:

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --override camera.sample_number=5 strategy.params.minimum_distance=3.0
```

Common options:

| Option | Default | Description |
| --- | --- | --- |
| `--dataset` | `GRScenes` | Dataset name under `--scene-dir`. |
| `--part` | `1` | Dataset part index. |
| `--usd` | required | USD folder id, for example `101` for `101_usd`. |
| `--specific` | unset | Restrict generation to one scene directory. |
| `--scene-dir` | `data/source` | Root directory containing dataset scene assets. |
| `--output-dir` | `output/camera_poses` | Root directory for generated trajectory JSON files. |
| `--cache-dir` | `output/scene_cache` | Root directory for parsed point-cloud caches. |
| `--override` | unset | Dotted scalar config overrides such as `camera.sample_number=5`. |
| `--retry-failed` | `false` | Regenerate scenes marked `failed` in the existing report. |
| `--force-reparse` | `false` | Ignore cached point clouds and parse USD files again. |

## Trajectory Configuration

Generation configs are YAML files. The loader first reads `configs/trajectory/default.yaml`, then deep-merges the selected strategy YAML, then applies `--override`.

```yaml
scene_map:
  grid_resolution: 0.05
  safe_distance: 0.20
  ceiling_offset: 1.8
  cluster_eps: 0.2
  cluster_safe_threshold: 0.05
  cluster_min_points: 1000
  min_overlap_ratio: 0.3

strategy:
  name: astar_nav
  params: {}

camera:
  pitch_deg: 0
  pitch_deg_range: [0, 15]
  height: 1.8
  height_range: [1.2, 1.7]
  sample_number: 20

postprocess:
  min_step_distance: 0.3
  min_step_angle: 0.15
  min_turn_distance: 0.15
  bspline_degree: 3
  bspline_step: 100
```

Supported strategies:

| Strategy | Parameters |
| --- | --- |
| `astar_nav` | `minimum_distance`, `use_optimizer`, `optimizer_clearance`, `optimizer_lambda_smooth`, `initial_sample_step` |
| `forward_motion` | `minimum_distance`, `max_retries`, `waypoint_spacing`, `min_wall_clearance` |

When `pitch_deg_range` or `height_range` is used, the value is sampled once per floor before post-processing trajectories on that floor.

## Generated Data

Trajectory files:

```text
output/camera_poses/{dataset}/part{part}/{usd}_usd/
  generation_report_{strategy}.json
  {scene_name}/{strategy}/
    f{floor_idx}_t{traj_idx}.json
```

Each `f{floor_idx}_t{traj_idx}.json` file is a list of camera frames:

```json
[
  [[x, y, z], [qw, qx, qy, qz]],
  [[x, y, z], [qw, qx, qy, qz]]
]
```

Positions are in meters. Quaternions use scalar-first order. The camera height is stored as absolute scene height: `floor_height + camera_height`.

The generation report is keyed by scene name:

```json
{
  "scene_00001": {
    "status": "success",
    "floors_detected": 1,
    "trajectories_generated": 20,
    "trajectories_attempted": 20,
    "failure_reasons": [],
    "prim_filter": {
      "valid_count": 123,
      "noise_count": 4,
      "noise_prims": [],
      "survival_rates": {}
    }
  }
}
```

Skipped scenes may only contain `status` and `reason`.

Parsed-scene caches are stored separately:

```text
output/scene_cache/{dataset}/part{part}/{usd}_usd/{scene_name}/
  scene_pcd.ply
  scene_metadata.json
```

## Render Trajectories

Rendering must run in an Isaac Sim Python environment.

```bash
python trajectory_tools/render_trajectory.py \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --strategy astar_nav
```

By default, rendering outputs `rgbd`. Select other output types with flags:

```bash
# RGB only
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb

# Depth only
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --depth

# RGBD plus instance segmentation
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb --depth --instance

# White-material shading
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading

# White-material shading with randomized lights
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading-randlight
```

Common options:

| Option | Default | Description |
| --- | --- | --- |
| `--scene` | unset | Render one scene by name. |
| `--scene-idx` | unset | Render one scene by sorted index. |
| `--trajectory-index` | unset | Render one trajectory index within each selected scene. |
| `--data-dir` | `data/source` | Root directory containing scene USD assets. |
| `--trajectory-dir` | `output/camera_poses` | Root directory containing generated trajectories. |
| `--output-dir` | `output/render` | Root directory for rendered outputs. |
| `--strategy` | `astar_nav` | One or more strategy names, or `all` to discover available strategies. |
| `--panorama` | `false` | Render 2048 x 1024 equirectangular frames instead of 800 x 400 perspective frames. |
| `--auto-expose` | `false` | Enable RTX histogram auto exposure. |
| `--camera-light` | `false` | Use camera lighting; `rgb` and `shading` outputs are suffixed with `_camlight`. |
| `--no-video` | `false` | Save frame files without MP4 videos. |
| `--light-per-trajectory` | `false` | Randomize lights separately for each trajectory. |

Rendering loads:

```text
data/source/{dataset}/part{part}/{usd}_usd/{scene_name}/{single_usd_file}.usd
output/camera_poses/{dataset}/part{part}/{usd}_usd/{scene_name}/{strategy}/f0_t0.json
```

Rendered outputs:

```text
output/render/{dataset}/part{part}/{usd}_usd/{scene_name}/{strategy}/{trajectory_name}/
  camera_poses.json
  rgb/*.jpg
  depth/*.npy
  instance/*_seg.pkl
  shading/*.jpg
  shading_randlight/*.jpg
  rgb.mp4
  shading.mp4
  shading_randlight.mp4
  camera_intrinsic.json
  camera_intrinsic_rgb.json
  camera_intrinsic_depth.json
  camera_intrinsic_instance.json
```

Output details:

| Type | Files | Notes |
| --- | --- | --- |
| `rgb` | `rgb/*.jpg`, `rgb.mp4`, `camera_intrinsic_rgb.json` | Standard RGB frames. |
| `rgbd` | `rgb/*.jpg`, `depth/*.npy`, `rgb.mp4`, `camera_intrinsic.json` | Selected by default or by `--rgb --depth`. |
| `depth` | `depth/*.npy`, `camera_intrinsic_depth.json` | Depth is saved as float16 meters. |
| `instance` | `instance/*_seg.pkl`, `camera_intrinsic_instance.json` | Pickle payload contains instance mask data and ID metadata. |
| `shading` | `shading/*.jpg`, `shading.mp4` | Uses the WhiteMode material setup. |
| `shading_randlight` | `shading_randlight/*.jpg`, `shading_randlight.mp4` | Randomized lighting; `light_params.json` is saved per scene/strategy by default or per trajectory with `--light-per-trajectory`. |

Re-running the same render command skips outputs that already contain the expected frame count and required metadata files.
