"""YAML configuration loader for trajectory generation."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import yaml

from .post_processor import PostProcessConfig
from .scene_map import SceneMapConfig

DEFAULT_YAML = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "configs",
    "trajectory",
    "default.yaml",
)


@dataclass
class StrategyConfig:
    name: str = "astar_nav"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class CameraConfig:
    pitch_deg: float | None = None
    pitch_deg_range: list[float] | None = None
    height: float | None = None
    height_range: list[float] | None = None
    sample_number: int | None = None

    def resolve_pitch_rad(self) -> float:
        if self.pitch_deg is not None:
            return float(np.deg2rad(self.pitch_deg))
        if self.pitch_deg_range is not None:
            return float(np.deg2rad(np.random.uniform(*self.pitch_deg_range)))
        return 0.0

    def resolve_height(self) -> float:
        if self.height is not None:
            return float(self.height)
        if self.height_range is not None:
            return float(np.random.uniform(*self.height_range))
        return 1.8


@dataclass
class TrajectoryGenerationConfig:
    scene_map: SceneMapConfig = field(default_factory=SceneMapConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    postprocess: PostProcessConfig = field(default_factory=PostProcessConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _apply_dot_overrides(config: dict, overrides: dict[str, Any]) -> dict:
    for key, value in overrides.items():
        target = config
        parts = key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return config


def _dict_to_config(config: dict) -> TrajectoryGenerationConfig:
    scene_map = SceneMapConfig(**config.get("scene_map", {}))
    strategy = StrategyConfig(**config.get("strategy", {}))
    camera = CameraConfig(**config.get("camera", {}))
    post_raw = config.get("postprocess", {})
    postprocess = PostProcessConfig(**{
        key: value
        for key, value in post_raw.items()
        if key in PostProcessConfig.__dataclass_fields__
    })
    return TrajectoryGenerationConfig(scene_map, strategy, camera, postprocess)


def load_config(
    yaml_path: str,
    overrides: dict[str, Any] | None = None,
) -> TrajectoryGenerationConfig:
    with open(os.path.normpath(DEFAULT_YAML)) as f:
        merged = yaml.safe_load(f) or {}

    with open(yaml_path) as f:
        strategy_config = yaml.safe_load(f) or {}

    _deep_merge(merged, copy.deepcopy(strategy_config))
    if overrides:
        _apply_dot_overrides(merged, overrides)
    return _dict_to_config(merged)
