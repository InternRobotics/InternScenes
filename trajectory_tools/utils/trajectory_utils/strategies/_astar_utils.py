"""Sampling and A* pathfinding utilities."""

from __future__ import annotations

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from ..geometry_tools import points_2d_distance
from ..scene_map import SceneMap

FINDER = AStarFinder(diagonal_movement=DiagonalMovement.always)


def sample_start_end(
    scene_map: SceneMap,
    minimum_distance: float = 5.0,
) -> tuple[bool, np.ndarray | None, np.ndarray | None, int, str]:
    weights = np.exp(scene_map.clusters_score / 0.2)
    probs = weights / weights.sum()
    cluster_idx = int(np.random.choice(len(scene_map.clusters_score), p=probs))

    cluster_points = np.asarray(scene_map.navigable_clusters[cluster_idx].points)
    pts_2d = cluster_points[:, :2]
    diameter = np.linalg.norm(pts_2d.max(0) - pts_2d.min(0))
    min_dist = min(minimum_distance, diameter - 1)

    start = cluster_points[np.random.choice(len(cluster_points))]
    distance = points_2d_distance(cluster_points, np.array([start]))
    candidates = np.where(distance > min_dist)[0]
    if len(candidates) == 0:
        reason = f"no valid endpoint: diameter={diameter:.1f}m, min_dist={min_dist:.1f}m"
        return False, None, None, cluster_idx, reason

    end = cluster_points[np.random.choice(candidates)]
    return True, start, end, cluster_idx, ""


def astar_path(
    scene_map: SceneMap,
    start: np.ndarray,
    end: np.ndarray,
) -> tuple[bool, np.ndarray, str]:
    start_idx = scene_map.point_to_grid(start)
    end_idx = scene_map.point_to_grid(end)

    if scene_map.decision_map[end_idx[0], end_idx[1]] == 0:
        nav_y, nav_x = np.where(scene_map.decision_map > 0)
        distance = np.sqrt((nav_y - end_idx[0]) ** 2 + (nav_x - end_idx[1]) ** 2)
        best = distance.argmin()
        end_idx[0], end_idx[1] = nav_y[best], nav_x[best]

    grid = Grid(matrix=scene_map.decision_map)
    path, _ = FINDER.find_path(
        grid.node(start_idx[1], start_idx[0]),
        grid.node(end_idx[1], end_idx[0]),
        grid,
    )
    if not path:
        reason = f"A* no path: ({start_idx[0]},{start_idx[1]}) -> ({end_idx[0]},{end_idx[1]})"
        return False, np.array([]), reason

    grid_points = np.array([[node.y, node.x] for node in path])
    return True, scene_map.grid_to_point(grid_points), ""
