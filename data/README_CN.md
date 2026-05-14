[English](README.md) | [中文](README_CN.md)

# InternScenes-Real2Sim 数据准备

## 数据下载

我们目前在 [Hugging Face](https://huggingface.co/datasets/InternRobotics/InternScenes) 托管数据集。发布的 3D 资产以 GLB 格式提供。

如果需要原始上游格式，例如 PartNet-Mobility 的 URDF 文件，请从官方来源下载原始数据：

1. 下载 Objaverse 数据：[HERE](https://objaverse.allenai.org/)。
2. 下载 HSSD 数据：[HERE](https://huggingface.co/datasets/hssd/hssd-models)。
3. 下载 3D-FUTURE 数据：[HERE](https://tianchi.aliyun.com/specials/promotion/alibaba-3d-future)。
4. 下载 PartNet-Mobility 数据：[HERE](https://sapien.ucsd.edu/browse)。

## 目录结构

请在仓库中按如下方式组织 Real2Sim 布局数据和 GLB 资产库。

```text
data/
  asset_library/                 # 场景合成使用的 GLB 资产
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
        StructureMesh/           # 地板和墙壁的 3D 网格
          wall.glb
        layout.json              # 场景布局标注
```

`layout.json` 保存单个场景中的物体标注，格式如下：

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

`model_uid` 会相对于 `data/asset_library/` 解析。例如，`partnet_mobility/39551` 指向本地资产库中对应的 PartNet-Mobility 资产目录。

# 轨迹与渲染数据

轨迹生成和渲染使用 [`trajectory_tools/README_CN.md`](../trajectory_tools/README_CN.md) 中说明的数据组织方式。默认目录如下：

```text
data/
  source/
    {dataset}/
      part{part}/
        {usd}_usd/
          {scene_name}/
            scene.usd            # scene 目录下唯一的直属 USD 文件
  env/
    default_no_specular.mdl
    WhiteMode.mdl
    default.png
output/
  camera_poses/                  # 生成的轨迹 JSON 文件
  scene_cache/                   # 解析后的场景点云缓存
  render/                        # 渲染得到的 RGB、深度、实例分割和 shading 结果
```

`data/source` 下的每个 scene 目录必须且只能包含一个直属 `.usd` 文件。如果某个 scene 目录中没有 USD 或存在多个 USD，轨迹生成和渲染会跳过该 scene，而不是自动选择其中一个文件。

生成命令、渲染命令、输出格式和配置细节请参阅[轨迹工具指南](../trajectory_tools/README_CN.md)。
