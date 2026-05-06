[English](README.md) | [中文](README_CN.md)

<p align="center">
<div style="text-align: center;">
    <img src="assets/teaser.png" alt="Teaser" width=100% >
</div>
<div align="center">

# InternScenes: 大规模交互式室内场景数据集

</div>
</p>
<div align="center">
    <a href='https://arxiv.org/abs/2509.10813'><img src='https://img.shields.io/badge/Paper-arXiv-%232986fc'></a> &nbsp;
    <a href='https://huggingface.co/datasets/InternRobotics/InternScenes'><img src='https://img.shields.io/badge/Data-HuggingFace-%23fe236d?&logo=huggingface'></a> &nbsp;
    <a href='https://marjordcpz.github.io/InternScenes.github.io'><img src='https://img.shields.io/badge/Home-Website-05a4a7?'></a> &nbsp;
</div>


## 简介

  <p>
      <strong>InternScenes</strong> 包含约 <strong>40,000 个多样化场景</strong>和 <strong>196 万个 3D 物体</strong>，涵盖 <strong>15 种常见场景类型</strong>和 <strong>288 个物体类别</strong>，规模约为现有数据集的 <strong>10 倍</strong>。
  </p>

## 亮点

  <div class="section">
    <p>现有 3D 场景数据集通常面临以下问题：</p>
    <ul>
      <li>多样性或可仿真性有限</li>
      <li>布局过于简化，缺少小物体</li>
      <li>严重的物体碰撞问题</li>
    </ul>
  </div>

  <div class="section">
    <p>InternScenes 集成了多种场景，特别保留了小物体以实现复杂布局，解决了碰撞问题，并进一步加入了交互式物体，确保了：</p>
    <ul>
      <li><strong>大规模</strong>：40,000 个多样化场景，包含 196 万个 3D 物体，涵盖 288 个物体类别。</li>
      <li><strong>真实布局</strong>：保留大量小物体，严格对齐真实世界扫描场景。</li>
      <li><strong>交互性</strong>：20% 的交互式物体，涵盖 16 种常见类型，如橱柜、微波炉、烤箱和冰箱。</li>
    </ul>
  </div>

  ### 哪些任务将受益于我们的数据集？
  <ul>
   <li> 3D 场景重建
   <li> 3D 场景理解
   <li> 场景布局生成
   <li> 具身导航
  </ul>

  ### 支持这些任务的内容有哪些？

   1. 便捷高效的场景渲染脚本；
   2. 详细的物体语义信息；
   3. 统一格式和坐标系的场景布局；
   4. 多样化的具身导航轨迹。

  关于数据集的使用，请参阅[教程](#教程)。

## 新闻
  - `2025/07` InternScenes-Real2Sim v1.0 发布。

## 目录
  - [简介](#简介)
  - [亮点](#亮点)
  - [新闻](#新闻)
  - [目录](#目录)
  - [快速开始](#快速开始)
  - [教程](#教程)
  - [待办事项](#待办事项)
  - [引用](#引用)
  - [许可证](#许可证)
  - [致谢](#致谢)


## 快速开始
### 安装

1. 克隆此仓库。

```bash
git clone https://github.com/InternRobotics/InternScenes.git
cd InternScenes
```

2. 创建环境并安装基本依赖。

```bash
conda create -n internscenes python=3.10 -y  
conda activate internscenes
pip install -r requirements.txt
```

3. （可选）安装 Isaac-Sim 4.1.0 以渲染 *.usd 文件和转换 *.glb 文件。
```bash
# 确保你的 conda 环境已激活。
pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu118
pip install isaacsim==4.1.0 isaacsim-extscache-physics==4.1.0 isaacsim-extscache-kit==4.1.0 isaacsim-extscache-kit-sdk==4.1.0 --extra-index-url https://pypi.nvidia.com
```

### 数据准备
请参阅[指南](https://github.com/InternRobotics/InternScenes/tree/master/data)了解下载和组织方式。

```shell
InternScenes-Real2Sim/
|-- Assets_library/                 # 场景资产库
  |-- objaverse/                      # 1. Objaverse 资产库    
  |-- hssd-models/                    # 2. HSSD 资产库 
  |-- 3D-FUTURE-model/                # 3. 3D-FUTURE 资产库
  |-- gr100/                          # 4. GRScenes-100 资产库
  |-- partNet-mobility/               # 5. PartNet-Mobility 资产库
  |-- gen-assets/                     # 6. 生成资产库
|-- Layout_info/                   
  |-- scan_id/
    |-- StructureMesh/              # 地板和墙壁的 3D 网格
      |-- wall.glb     
    |-- layout.json                 # 场景布局 json
```

布局格式如下：
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
    },
   ...
]
```

## 教程
我们提供了一个简单的教程[在此](https://github.com/InternRobotics/InternScenes/blob/master/tutorial/tutorial.ipynb)，作为数据集可视化和基本用法的指南。欢迎尝试并提出建议！

### 轨迹生成与渲染
关于生成相机轨迹和在 Isaac Sim 中渲染场景，请参阅[轨迹工具](trajectory_tools/README_CN.md)。


## 待办事项
 - [x] 发布 InternScenes-Real2Sim。
 - [x] 发布各场景的轨迹和渲染脚本。
 - [x] 发布论文。
 - [x] 完善 InternScenes-Real2Sim 构建代码。
 - [x] 完善 InternScenes-Synthetic 构建代码。
 - [ ] 发布 InternScenes-Synthetic。

## 引用
```BibTex
@inproceedings{InternScenes,
  title={InternScenes: A Large-scale Interactive Indoor Scene Dataset with Realistic Layouts},
  author={Zhong, Weipeng and Cao, Peizhou and Jin, Yichen and Li, Luo and Cai, Wenzhe and Lin, Jingli and Lyu, Zhaoyang and Wang, Tai and Dai, Bo and Xu, Xudong and Pang, Jiangmiao},
  year={2025},
  booktitle={arXiv},
}
```
## 许可证

<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc-sa/4.0/80x15.png" /></a>

本作品采用<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">知识共享署名-非商业性使用-相同方式共享 4.0 国际许可协议</a>进行许可。

## 致谢
- [EmbodiedScan](https://github.com/OpenRobotLab/EmbodiedScan)：我们检索的场景基于 EmbodiedScan 的标注，其中包含大量小物体的 9-DoF 边界框。
- [InternUtopia](https://github.com/OpenRobotLab/GRUtopia)（前身为 GRUtopia）：本仓库中部分高质量 3D 资产文件（*.usd）来源于此。
- [Hunyuan3D-2.1](https://github.com/tencent-hunyuan/hunyuan3d-2.1)：部分 3D 资产的纹理由该模型生成。
- [HSSD](https://github.com/3dlg-hcvc/hssd)：精选了该项目中的物体资产用于构建我们的资产库。
- [PartNet-Mobility](https://github.com/haosulab/SAPIEN)：精选了该项目中的物体资产用于构建我们的资产库。
- [Objaverse](https://objaverse.allenai.org/)：精选了该项目中的物体资产用于构建我们的资产库。
