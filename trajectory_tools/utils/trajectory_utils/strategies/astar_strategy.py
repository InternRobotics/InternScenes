"""A* point-to-point navigation strategy."""

from __future__ import annotations

import numpy as np

from ..path_optimizer import optimize_trajectory
from ..scene_map import SceneMap
from . import register_strategy
from ._astar_utils import astar_path, sample_start_end
from .base_strategy import BaseStrategy, StrategyResult

DEFAULTS = {
    "minimum_distance": 5.0,
    "use_optimizer": True,
    "optimizer_clearance": 0.5,
    "optimizer_lambda_smooth": 0.3,
    "initial_sample_step": 3,
}


@register_strategy("astar_nav")
class AStarStrategy(BaseStrategy):
    def __init__(self, params: dict | None = None) -> None:
        super().__init__({**DEFAULTS, **(params or {})})

    def generate(self, scene_map: SceneMap) -> tuple[bool, StrategyResult]:
        ok, start, end, cluster_idx, reason = sample_start_end(
            scene_map,
            self.params["minimum_distance"],
        )
        if not ok:
            return False, StrategyResult(np.array([]), failure_reason=reason)

        ok, waypoints, reason = astar_path(scene_map, start, end)
        if not ok:
            return False, StrategyResult(np.array([]), failure_reason=reason)

        step = self.params["initial_sample_step"]
        path = waypoints[::step] if step > 1 else waypoints
        if self.params["use_optimizer"]:
            path = optimize_trajectory(
                path[:, :2],
                scene_map.esdf,
                self.params["optimizer_lambda_smooth"],
                scene_map.min_bound[0],
                scene_map.max_bound[0],
                scene_map.min_bound[1],
                scene_map.max_bound[1],
                scene_map.config.grid_resolution,
                self.params["optimizer_clearance"],
            )
        return True, StrategyResult(path, metadata={"cluster_index": cluster_idx})
