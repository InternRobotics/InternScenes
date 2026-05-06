[English](README.md) | [中文](README_CN.md)

# InternScenes Synthetic

本目录用于说明 InternScenes-Synthetic 数据准备流程中使用的配套工具。整体流程分为两个模块：3ds Max 文件预处理和场景实例标注。

## 1. 3ds Max 文件预处理

仓库链接：
[`MarjordCpz/max-processing-tools`](https://github.com/MarjordCpz/max-processing-tools)

该模块用于在标注前预处理原始 3ds Max 场景文件。它支持将 `.max` 或 `.usd` 场景批量转换为 USD、OBJ、HDF5
等下游格式，并提供断点续跑、转换报告和可选的场景清理等功能。

安装、配置和具体使用方式请参考上述仓库。

## 2. 场景实例标注工具

仓库链接：
[`MarjordCpz/scene-instance-annotator`](https://github.com/MarjordCpz/scene-instance-annotator)

该模块用于对预处理后的场景网格进行标注。它支持 HDF5 格式场景数据的语义实例分组、结构语义标签、标注审阅和 QA
检查。

编译方式、快捷键、标注流程和结果管理请参考上述仓库。

## 推荐使用顺序

1. 先使用预处理工具将原始场景文件转换为可标注的场景数据。
2. 再使用标注工具完成语义实例标注、审阅和结果导出。
