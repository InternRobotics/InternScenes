# InternScenes_Gen

[![English](https://img.shields.io/badge/lang-English-blue.svg)](./README.md)
[![中文](https://img.shields.io/badge/lang-Chinese-red.svg)](./README_zh-CN.md)

`InternScenes_Gen` 是 InternScenes 中由程序生成的场景子集。本目录提供了一个轻量级场景组合脚本 `compose_scene.py`，用于根据发布的 layout 文件和 asset 文件重建 GLB 场景。

## 目录结构

下载 release 数据后，目录应组织为：

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

每个 `layout.json` 包含物体实例的 `model_uid` 和 `bbox`。脚本会从 `Asset_Library` 中读取对应的 `whole.glb`，根据 layout 里的变换信息放回场景，可选加入房间结构 mesh，最后导出完整的 GLB 场景。

## 依赖

```bash
pip install numpy trimesh
```

如果需要保留材质和纹理，请确保下载的 `whole.glb` 文件中包含相应的视觉资源。

## 组合单个场景

在当前目录下运行：

```bash
python compose_scene.py --room-id bathroom/0
```

默认输出路径为：

```text
InternScenes_Gen/composed_scenes/bathroom_0.glb
```

也可以显式指定数据目录和输出路径：

```bash
python compose_scene.py --data-root /path/to/InternScenes_Gen --room-id bathroom/0 --output-path /path/to/output/bathroom_0.glb
```

## 批量组合所有场景

`total_scene_ids.json` 中包含所有发布的生成场景 id。批量组合所有场景：

```bash
python compose_scene.py --all --workers 8
```

使用自定义场景 id 列表：

```bash
python compose_scene.py --room-ids-file /path/to/scene_ids.json --output-dir /path/to/composed_scenes
```

自定义场景 id 文件应为 JSON 字符串列表，例如：

```json
[
  "bathroom/0",
  "bedroom/10000"
]
```

## 常用参数

```text
--data-root        InternScenes_Gen 数据目录。
--room-id          指定一个场景 id，可传入多次。
--room-ids-file    包含场景 id 列表的 JSON 文件。
--all              使用 total_scene_ids.json 组合全部场景。
--output-dir       批量导出 GLB 的输出目录。
--output-path      单个场景的输出 GLB 路径。
--workers          并行加载资产的线程数。
--no-texture       导出时移除纹理 visual 信息。
--no-structure     不加入 StructureMesh/StructureMesh.glb。
```

## 说明

- `IM/...` 资产会根据 layout bbox 做 canonical pose 校正、缩放、旋转和平移。
- `Infinigen_asset/...` 资产默认已经在预处理阶段导出到场景坐标系中。
- 最终组合出的 GLB 使用 release 数据约定的 Y-up 坐标。
- 脚本会保留多部件 GLB 内部的 scene graph transform。
