[English](README.md) | [中文](README_CN.md)

# InternScenes Synthetic

This directory provides links to the companion tools used in the
InternScenes-Synthetic data preparation workflow. The workflow is divided into
two modules: 3ds Max file preprocessing and scene instance annotation.

## 1. 3ds Max File Preprocessing

Repository:
[`MarjordCpz/max-processing-tools`](https://github.com/MarjordCpz/max-processing-tools)

This module is used to preprocess raw 3ds Max scene files before annotation. It
supports batch conversion from `.max` or `.usd` assets into downstream formats
such as USD, OBJ, and HDF5, and provides utilities for resumable processing,
conversion reports, and optional scene cleanup.

Please refer to the repository above for installation, configuration, and usage
details.

## 2. Scene Instance Annotation Tool

Repository:
[`MarjordCpz/scene-instance-annotator`](https://github.com/MarjordCpz/scene-instance-annotator)

This module is used to annotate the preprocessed scene meshes. It supports
semantic instance grouping, structural labels, annotation review, and QA for
HDF5-format scene data.

Please refer to the repository above for build instructions, keyboard shortcuts,
annotation workflow, and result management.

## Recommended Order

1. Use the preprocessing tools to convert raw scene files into annotation-ready
   scene data.
2. Use the annotation tool to create, review, and export semantic instance
   annotations.
