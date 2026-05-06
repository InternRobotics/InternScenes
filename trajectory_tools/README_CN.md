[English](README.md) | [中文](README_CN.md)

# 轨迹工具

`trajectory_tools` 提供 InternScenes 相机轨迹的发布流程：

1. 从 USD 场景资产生成相机位姿轨迹。
2. 在 Isaac Sim 中沿轨迹渲染 RGB、深度、实例分割、shading 和随机光照 shading 数据。

本文档只说明数据约定、配置结构和命令用法。环境配置请参考仓库根目录 README。

## 数据目录

本文档中的命令默认从仓库根目录运行。默认路径都相对于当前工作目录解析。

```text
data/
  source/
    GRScenes/
      part1/
        101_usd/
          scene_00001/
            scene.usd          # scene 目录下唯一的 USD 文件
  env/
    default_no_specular.mdl
    WhiteMode.mdl
    default.png
output/
  camera_poses/
  scene_cache/
  render/
```

每个 scene 目录必须且只能包含一个直属 `.usd` 文件。轨迹生成和渲染都会读取这个文件。如果某个 scene 目录中没有 USD 或存在多个 USD，代码会跳过该 scene，而不是任意选择一个文件。

`data/env` 中是渲染和材质引用修复使用的材质资源。

## 生成轨迹

为 `data/source/{dataset}/part{part}/{usd}_usd/` 下的所有 scene 生成轨迹：

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101
```

只处理一个 scene：

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --specific scene_00001
```

使用直线前进策略：

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/forward_motion.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101
```

从命令行覆盖标量 YAML 参数：

```bash
python trajectory_tools/generate_trajectory.py \
  --config trajectory_tools/configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --override camera.sample_number=5 strategy.params.minimum_distance=3.0
```

常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--dataset` | `GRScenes` | `--scene-dir` 下的数据集名称。 |
| `--part` | `1` | 数据集 part 编号。 |
| `--usd` | 必填 | USD 文件夹编号，例如 `101` 对应 `101_usd`。 |
| `--specific` | 未设置 | 只生成指定 scene 的轨迹。 |
| `--scene-dir` | `data/source` | 场景资产根目录。 |
| `--output-dir` | `output/camera_poses` | 轨迹 JSON 输出根目录。 |
| `--cache-dir` | `output/scene_cache` | 场景点云解析缓存根目录。 |
| `--override` | 未设置 | 点号形式的标量配置覆盖，例如 `camera.sample_number=5`。 |
| `--retry-failed` | `false` | 重新生成 report 中标记为 `failed` 的 scene。 |
| `--force-reparse` | `false` | 忽略已有点云缓存，重新解析 USD。 |

## 轨迹配置

轨迹配置使用 YAML。加载顺序为：先读取 `configs/trajectory/default.yaml`，再 deep-merge 指定的策略 YAML，最后应用 `--override`。

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

支持的策略：

| 策略 | 参数 |
| --- | --- |
| `astar_nav` | `minimum_distance`, `use_optimizer`, `optimizer_clearance`, `optimizer_lambda_smooth`, `initial_sample_step` |
| `forward_motion` | `minimum_distance`, `max_retries`, `waypoint_spacing`, `min_wall_clearance` |

使用 `pitch_deg_range` 或 `height_range` 时，代码会在每层楼 post-process 前采样一次；同一楼层内生成的多条轨迹共享该次采样值。

## 生成数据

轨迹文件结构：

```text
output/camera_poses/{dataset}/part{part}/{usd}_usd/
  generation_report_{strategy}.json
  {scene_name}/{strategy}/
    f{floor_idx}_t{traj_idx}.json
```

每个 `f{floor_idx}_t{traj_idx}.json` 文件都是相机帧列表：

```json
[
  [[x, y, z], [qw, qx, qy, qz]],
  [[x, y, z], [qw, qx, qy, qz]]
]
```

位置单位是米。四元数使用 scalar-first 顺序。相机高度保存为场景中的绝对高度：`floor_height + camera_height`。

生成 report 以 scene 名称为 key：

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

被跳过的 scene 可能只包含 `status` 和 `reason`。

场景解析缓存单独保存：

```text
output/scene_cache/{dataset}/part{part}/{usd}_usd/{scene_name}/
  scene_pcd.ply
  scene_metadata.json
```

## 渲染轨迹

渲染必须在 Isaac Sim Python 环境中运行。

```bash
python trajectory_tools/render_trajectory.py \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --strategy astar_nav
```

默认输出 `rgbd`。可以用参数选择其他输出类型：

```bash
# 只输出 RGB
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb

# 只输出深度
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --depth

# 输出 RGBD 和实例分割
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb --depth --instance

# WhiteMode 材质 shading
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading

# WhiteMode 材质和随机光照 shading
python trajectory_tools/render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading-randlight
```

常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--scene` | 未设置 | 按 scene 名称只渲染一个 scene。 |
| `--scene-idx` | 未设置 | 按排序后的 scene index 只渲染一个 scene。 |
| `--trajectory-index` | 未设置 | 在每个选中 scene 中只渲染第 N 条轨迹。 |
| `--data-dir` | `data/source` | 场景 USD 资产根目录。 |
| `--trajectory-dir` | `output/camera_poses` | 已生成轨迹的根目录。 |
| `--output-dir` | `output/render` | 渲染输出根目录。 |
| `--strategy` | `astar_nav` | 一个或多个策略名称，也可以使用 `all` 自动发现已有策略。 |
| `--panorama` | `false` | 输出 2048 x 1024 equirectangular 图像，而不是 800 x 400 透视图。 |
| `--auto-expose` | `false` | 启用 RTX histogram 自动曝光。 |
| `--camera-light` | `false` | 使用 camera lighting；`rgb` 和 `shading` 输出名会带 `_camlight` 后缀。 |
| `--no-video` | `false` | 只保存帧文件，不保存 MP4。 |
| `--light-per-trajectory` | `false` | 为每条轨迹单独随机化光照。 |

渲染读取：

```text
data/source/{dataset}/part{part}/{usd}_usd/{scene_name}/{single_usd_file}.usd
output/camera_poses/{dataset}/part{part}/{usd}_usd/{scene_name}/{strategy}/f0_t0.json
```

渲染输出：

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

输出类型说明：

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| `rgb` | `rgb/*.jpg`, `rgb.mp4`, `camera_intrinsic_rgb.json` | 标准 RGB 帧。 |
| `rgbd` | `rgb/*.jpg`, `depth/*.npy`, `rgb.mp4`, `camera_intrinsic.json` | 默认输出，也可以通过 `--rgb --depth` 选择。 |
| `depth` | `depth/*.npy`, `camera_intrinsic_depth.json` | 深度以 float16 保存，单位为米。 |
| `instance` | `instance/*_seg.pkl`, `camera_intrinsic_instance.json` | Pickle 内容包含 instance mask 和 ID 元数据。 |
| `shading` | `shading/*.jpg`, `shading.mp4` | 使用 WhiteMode 材质设置。 |
| `shading_randlight` | `shading_randlight/*.jpg`, `shading_randlight.mp4` | 随机光照；默认在 scene/strategy 目录保存 `light_params.json`，使用 `--light-per-trajectory` 时保存在每条轨迹目录下。 |

重新运行相同渲染命令时，已具备预期帧数和必要元数据文件的输出会自动跳过。
