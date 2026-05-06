[English](#english) | [中文](#中文)

---

# English

## Trajectory Generation and Rendering Pipeline

This directory is a streamlined distribution that contains two things:

1. Generate camera trajectory JSON files from USD scenes.
2. Render RGB, RGBD, depth, instance segmentation, shading, and other data along trajectories in Isaac Sim.

### Environment

Trajectory generation depends on Python scientific computing and USD/Open3D environments; rendering must run in an Isaac Sim Python environment that can import `isaacsim`, `omni`, and `pxr`.

Install Python dependencies first:

```bash
pip install -r requirements.txt
```

Isaac Sim, USD Python bindings, and NVIDIA `omni` modules are typically provided by the Isaac Sim environment and are not recommended to install via `pip` separately.

### Data Directory

Default directory organization:

```text
trajectory_tools/
data/
  source/
    GRScenes/
      part1/
        101_usd/
          scene_00001/
            scene.usd          # Trajectory generation reads: non-copy USD
            scene_copy.usd     # Rendering reads: filename must contain _copy.usd
data/
  env/
    default_no_specular.mdl
    WhiteMode.mdl
    default.png
output/
  camera_poses/
  scene_cache/
  render/
```

If your data is not in the default path, you can specify with `--scene-dir`, `--output-dir`, `--cache-dir`, `--data-dir`, `--trajectory-dir`.

### Generate Trajectories

Run from the `trajectory_tools/` directory:

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101
```

Process a single scene:

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --part 1 \
  --usd 101 \
  --specific scene_00001
```

Use the forward motion strategy:

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/forward_motion.yaml \
  --part 1 \
  --usd 101
```

Override YAML parameters:

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --part 1 \
  --usd 101 \
  --override camera.sample_number=5 strategy.params.minimum_distance=3.0
```

Optional shortlist CSV:

```csv
usd_id,scene_id,rating
101,scene_00001,3
101,scene_00002,2
```

Run with shortlist:

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --part 1 \
  --usd 101 \
  --shortlist path/to/scene_shortlist.csv \
  --min-rating 3
```

Trajectory output:

```text
output/camera_poses/GRScenes/part1/101_usd/scene_00001/astar_nav/f0_t0.json
output/camera_poses/GRScenes/part1/101_usd/generation_report_astar_nav.json
```

Single-frame trajectory format:

```json
[
  [x, y, z],
  [qw, qx, qy, qz]
]
```

Position units are meters; quaternion is in scalar-first order.

### Rendering

Rendering must run in the Isaac Sim Python environment:

```bash
python render_trajectory.py \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --strategy astar_nav
```

Default renders RGBD. Select other output types:

```bash
# RGB
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb

# Depth
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --depth

# RGB + depth + instance
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb --depth --instance

# White material shading
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading

# Shading with randomized lights
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading-randlight
```

Common options:

```bash
# Panorama rendering, output 2048 x 1024 equirectangular image
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --panorama

# Render only one scene
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --scene scene_00001

# Render the Nth trajectory in a scene
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --trajectory-index 0

# Skip MP4, keep only frame files
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --no-video
```

Rendering output:

```text
output/render/GRScenes/part1/101_usd/scene_00001/astar_nav/f0_t0/
  camera_poses.json
  camera_intrinsic.json
  rgb/
    0.jpg
  depth/
    0.npy
  instance/
    0_seg.pkl
  shading/
    0.jpg
  rgb.mp4
```

Output type descriptions:

| Type | Files | Description |
| --- | --- | --- |
| `rgb` | `.jpg`, `.mp4` | Standard RGB |
| `rgbd` | `rgb/*.jpg`, `depth/*.npy`, `rgb.mp4` | RGB and depth together |
| `depth` | `.npy` | float16 depth in meters |
| `instance` | `*_seg.pkl` | Instance mask and ID mapping |
| `shading` | `.jpg`, `.mp4` | Shading under WhiteMode material |
| `shading_randlight` | `.jpg`, `.mp4`, `light_params.json` | Shading with randomized lighting |

Re-running the same command automatically skips already-completed trajectory outputs.

---

# 中文

## 轨迹生成与渲染流水线

这个目录是一个精简发布版，只包含两件事：

1. 从 USD 场景生成相机轨迹 JSON。
2. 在 Isaac Sim 中沿轨迹渲染 RGB、RGBD、depth、instance、shading 等数据。

### 环境

轨迹生成依赖 Python 科学计算和 USD/Open3D 环境；渲染必须在可导入 `isaacsim`、`omni`、`pxr` 的 Isaac Sim Python 环境中运行。

可先安装普通 Python 依赖：

```bash
pip install -r requirements.txt
```

Isaac Sim、USD Python 绑定和 NVIDIA `omni` 模块通常由 Isaac Sim 环境提供，不建议通过 `pip` 单独安装。

### 数据目录

默认目录组织如下：

```text
trajectory_tools/
data/
  source/
    GRScenes/
      part1/
        101_usd/
          scene_00001/
            scene.usd          # 轨迹生成读取：非 copy USD
            scene_copy.usd     # 渲染读取：文件名需包含 _copy.usd
data/
  env/
    default_no_specular.mdl
    WhiteMode.mdl
    default.png
output/
  camera_poses/
  scene_cache/
  render/
```

如果你的数据不在默认路径，可以用 `--scene-dir`、`--output-dir`、`--cache-dir`、`--data-dir`、`--trajectory-dir` 指定。

### 生成轨迹

在 `trajectory_tools/` 下运行：

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --dataset GRScenes \
  --part 1 \
  --usd 101
```

只处理一个场景：

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --part 1 \
  --usd 101 \
  --specific scene_00001
```

使用直线前进策略：

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/forward_motion.yaml \
  --part 1 \
  --usd 101
```

覆盖 YAML 参数：

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --part 1 \
  --usd 101 \
  --override camera.sample_number=5 strategy.params.minimum_distance=3.0
```

可选 shortlist CSV：

```csv
usd_id,scene_id,rating
101,scene_00001,3
101,scene_00002,2
```

运行时添加：

```bash
python generate_trajectory.py \
  --config configs/trajectory/strategy/astar_nav.yaml \
  --part 1 \
  --usd 101 \
  --shortlist path/to/scene_shortlist.csv \
  --min-rating 3
```

轨迹输出：

```text
output/camera_poses/GRScenes/part1/101_usd/scene_00001/astar_nav/f0_t0.json
output/camera_poses/GRScenes/part1/101_usd/generation_report_astar_nav.json
```

单帧轨迹格式：

```json
[
  [x, y, z],
  [qw, qx, qy, qz]
]
```

其中位置单位为米，四元数为 scalar-first 顺序。

### 渲染

渲染需要在 Isaac Sim Python 环境中运行：

```bash
python render_trajectory.py \
  --dataset GRScenes \
  --part 1 \
  --usd 101 \
  --strategy astar_nav
```

默认渲染 RGBD。选择其他输出类型：

```bash
# RGB
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb

# Depth
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --depth

# RGB + depth + instance
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --rgb --depth --instance

# White material shading
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading

# Shading with randomized lights
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --shading-randlight
```

常用选项：

```bash
# 全景渲染，输出 2048 x 1024 equirectangular 图像
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --panorama

# 只渲染一个场景
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --scene scene_00001

# 渲染一个场景中的第 N 条轨迹
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --trajectory-index 0

# 跳过 MP4，只保留帧文件
python render_trajectory.py --part 1 --usd 101 --strategy astar_nav --no-video
```

渲染输出：

```text
output/render/GRScenes/part1/101_usd/scene_00001/astar_nav/f0_t0/
  camera_poses.json
  camera_intrinsic.json
  rgb/
    0.jpg
  depth/
    0.npy
  instance/
    0_seg.pkl
  shading/
    0.jpg
  rgb.mp4
```

输出类型说明：

| 类型 | 文件 | 说明 |
| --- | --- | --- |
| `rgb` | `.jpg`, `.mp4` | 普通 RGB |
| `rgbd` | `rgb/*.jpg`, `depth/*.npy`, `rgb.mp4` | RGB 和深度一起输出 |
| `depth` | `.npy` | float16 深度，单位米 |
| `instance` | `*_seg.pkl` | instance mask 和 id 映射 |
| `shading` | `.jpg`, `.mp4` | WhiteMode 材质下的 shading |
| `shading_randlight` | `.jpg`, `.mp4`, `light_params.json` | 随机光照 shading |

重新运行同一命令时，已完成的轨迹输出会自动跳过。
