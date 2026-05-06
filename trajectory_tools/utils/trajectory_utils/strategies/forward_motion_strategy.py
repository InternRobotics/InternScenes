"""Straight-line forward-motion trajectory strategy."""

from __future__ import annotations

import numpy as np

from ..scene_map import SceneMap
from . import register_strategy
from ._astar_utils import sample_start_end
from .base_strategy import BaseStrategy, StrategyResult

DEFAULTS = {
    "minimum_distance": 5.0,
    "max_retries": 50,
    "waypoint_spacing": 0.3,
    "min_wall_clearance": 0.15,
}


def _interpolate_line(start: np.ndarray, end: np.ndarray, spacing: float) -> np.ndarray:
    distance = np.linalg.norm(end[:2] - start[:2])
    count = max(int(distance / spacing), 2)
    t = np.linspace(0, 1, count)
    return start[:2][None] + t[:, None] * (end[:2] - start[:2])[None]


def _line_is_navigable(
    points: np.ndarray,
    scene_map: SceneMap,
    min_clearance: float,
) -> bool:
    grid_indices = scene_map.point_to_grid(points)
    h, w = scene_map.esdf.shape
    gi = np.clip(grid_indices[:, 0], 0, h - 1)
    gj = np.clip(grid_indices[:, 1], 0, w - 1)
    return bool(np.all(scene_map.esdf[gi, gj] > min_clearance))


@register_strategy("forward_motion")
class ForwardMotionStrategy(BaseStrategy):
    def __init__(self, params: dict | None = None) -> None:
        super().__init__({**DEFAULTS, **(params or {})})

    def generate(self, scene_map: SceneMap) -> tuple[bool, StrategyResult]:
        for _ in range(self.params["max_retries"]):
            ok, start, end, cluster_idx, _ = sample_start_end(
                scene_map,
                self.params["minimum_distance"],
            )
            if not ok:
                continue

            points = _interpolate_line(start, end, self.params["waypoint_spacing"])
            if not _line_is_navigable(points, scene_map, self.params["min_wall_clearance"]):
                continue

            return True, StrategyResult(
                points,
                metadata={"cluster_index": cluster_idx, "postprocess_mode": "direct"},
            )

        reason = f"no navigable straight path found after {self.params['max_retries']} attempts"
        return False, StrategyResult(np.array([]), failure_reason=reason)
