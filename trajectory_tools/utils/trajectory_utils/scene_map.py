"""Grid map and navigable cluster extraction for trajectory generation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import open3d as o3d
from scipy.spatial import ConvexHull
from shapely.geometry import Polygon
from skimage.morphology import dilation, erosion

from .geometry_tools import numpy_2d_distance, pointcloud_2d_distance


@dataclass
class SceneMapConfig:
    grid_resolution: float = 0.05
    safe_distance: float = 0.20
    ceiling_offset: float = 1.8
    cluster_eps: float = 0.2
    cluster_safe_threshold: float = 0.05
    cluster_min_points: int = 1000
    min_overlap_ratio: float = 0.3


class SceneMap:
    def __init__(self, config: SceneMapConfig | None = None) -> None:
        self.config = config or SceneMapConfig()
        self.min_bound: np.ndarray | None = None
        self.max_bound: np.ndarray | None = None
        self.decision_map: np.ndarray | None = None
        self.esdf: np.ndarray | None = None
        self.safe_value: np.ndarray | None = None
        self.navigable_pcd: o3d.geometry.PointCloud | None = None
        self.navigable_clusters: list[o3d.geometry.PointCloud] = []
        self.clusters_score: np.ndarray | None = None

    def build(
        self,
        floor_height: float,
        robot_height: float,
        scene_pcd: o3d.geometry.PointCloud,
    ) -> None:
        cfg = self.config
        scene_points = np.asarray(scene_pcd.points)
        z = scene_points[:, 2]
        floor_slice = (z < floor_height + cfg.ceiling_offset) & (z > floor_height - 0.1)
        scene_pcd = scene_pcd.select_by_index(np.nonzero(floor_slice)[0])
        scene_points = np.asarray(scene_pcd.points)
        if len(scene_points) == 0:
            raise ValueError("empty point-cloud slice for floor")
        z = scene_points[:, 2]

        nav_mask = (z < floor_height + 0.1) & (z > floor_height - 0.1)
        self.navigable_pcd = scene_pcd.select_by_index(np.nonzero(nav_mask)[0])
        if len(self.navigable_pcd.points) == 0:
            raise ValueError("no navigable floor points")

        obs_mask = (z > floor_height + 0.2) & (z < floor_height + 2 * robot_height)
        obstacle_pcd = scene_pcd.select_by_index(np.nonzero(obs_mask)[0])
        obstacle_ds = obstacle_pcd.voxel_down_sample(cfg.grid_resolution)

        if len(obstacle_ds.points) == 0:
            obstacle_distance = np.full(len(self.navigable_pcd.points), cfg.safe_distance * 2)
        else:
            obstacle_distance = pointcloud_2d_distance(self.navigable_pcd, obstacle_ds)
        max_distance = obstacle_distance.max() + 1e-6
        too_close = obstacle_distance < cfg.safe_distance
        self.safe_value = (1 - too_close) * (obstacle_distance / max_distance)
        colors = np.column_stack((
            1.0 - self.safe_value,
            self.safe_value,
            np.zeros_like(self.safe_value),
        ))
        self.navigable_pcd.colors = o3d.utility.Vector3dVector(colors)

        self.max_bound = scene_points.max(axis=0)
        self.min_bound = scene_points.min(axis=0)
        self.decision_map = self._points_to_map(
            np.asarray(self.navigable_pcd.points),
            self.safe_value,
        )
        self._to_esdf(self.decision_map)
        self.navigable_clusters = self._cluster_navigable_points()

        cluster_sizes = np.array([len(cluster.points) for cluster in self.navigable_clusters])
        self.clusters_score = (
            (cluster_sizes / cluster_sizes.max()) + 1.0
            if len(cluster_sizes) > 0
            else np.array([])
        )

    def point_to_grid(self, point: np.ndarray) -> np.ndarray:
        if point.ndim == 1:
            return np.floor(
                (point[:2] - self.min_bound[:2]) / self.config.grid_resolution
            ).astype(np.int32)
        return np.floor(
            (point[:, :2] - self.min_bound[:2]) / self.config.grid_resolution
        ).astype(np.int32)

    def grid_to_point(self, grid: np.ndarray) -> np.ndarray:
        res = self.config.grid_resolution
        if grid.ndim == 1:
            g = np.array([*grid, 1], dtype=np.float32)
            return g * res + self.min_bound
        g = np.concatenate((grid, np.ones((grid.shape[0], 1))), axis=-1)
        return g * res + self.min_bound[np.newaxis, :]

    def _points_to_map(self, points: np.ndarray, values: np.ndarray) -> np.ndarray:
        res = self.config.grid_resolution
        dim_2d = np.ceil((self.max_bound[:2] - self.min_bound[:2]) / res).astype(int)
        dim_2d = np.maximum(dim_2d, 1)

        cost = np.full(tuple(dim_2d), 10.0, dtype=np.float32)
        idx = np.floor((points[:, :2] - self.min_bound[:2]) / res).astype(int)
        idx = np.clip(idx, 0, dim_2d - 1)
        np.minimum.at(cost, (idx[:, 0], idx[:, 1]), values)

        cost[(cost == 0) | (cost >= 10)] = 0
        cost[cost > 0] = 1
        return erosion(dilation(dilation(cost))).astype(np.float32)

    def _map_to_points(self, obstacle_map: np.ndarray) -> tuple:
        obs_y, obs_x = np.where(obstacle_map == 0)
        nav_y, nav_x = np.where(obstacle_map > 0)
        obs_coords = np.column_stack((obs_x, obs_y)).astype(np.float32)
        nav_coords = np.column_stack((nav_x, nav_y)).astype(np.float32)
        obs_pts = obs_coords * self.config.grid_resolution + self.min_bound[:2]
        nav_pts = nav_coords * self.config.grid_resolution + self.min_bound[:2]
        return obs_pts, nav_pts, (obs_y, obs_x), (nav_y, nav_x)

    def _to_esdf(self, obstacle_map: np.ndarray) -> None:
        obs_pts, nav_pts, obs_idx, nav_idx = self._map_to_points(obstacle_map)
        esdf = np.zeros(obstacle_map.shape)
        if len(obs_pts) == 0:
            esdf[nav_idx] = self.config.safe_distance * 2
        elif len(nav_pts) == 0:
            esdf[obs_idx] = -self.config.safe_distance * 2
        else:
            esdf[nav_idx] = numpy_2d_distance(nav_pts, obs_pts)
            esdf[obs_idx] = -numpy_2d_distance(obs_pts, nav_pts)
        self.esdf = esdf

    def _cluster_navigable_points(self) -> list[o3d.geometry.PointCloud]:
        cfg = self.config
        available = self.navigable_pcd.select_by_index(
            np.where(self.safe_value > cfg.cluster_safe_threshold)[0]
        )
        wall = self.navigable_pcd.select_by_index(
            np.where(self.safe_value < cfg.cluster_safe_threshold)[0]
        )
        wall_pts_2d = np.asarray(wall.points)[:, :2]

        wall_poly = None
        if len(wall_pts_2d) >= 3:
            try:
                wall_hull = ConvexHull(wall_pts_2d)
                wall_poly = Polygon(wall_pts_2d[wall_hull.vertices])
            except Exception as exc:
                print(f"[SceneMap] wall convex hull failed: {exc}")

        labels = np.array(available.cluster_dbscan(eps=cfg.cluster_eps, min_points=20))
        clusters = []
        for label in np.unique(labels):
            cluster = available.select_by_index(np.where(labels == label)[0])
            pts = np.asarray(cluster.points)
            if pts.shape[0] < cfg.cluster_min_points:
                continue
            try:
                hull = ConvexHull(pts[:, :2])
                poly = Polygon(pts[:, :2][hull.vertices])
            except Exception:
                continue

            if wall_poly is None:
                overlap = 1.0
            else:
                overlap = wall_poly.intersection(poly).area / poly.area if poly.area > 0 else 0.0
            if overlap < cfg.min_overlap_ratio:
                continue

            color = np.random.rand(1, 3)
            cluster.colors = o3d.utility.Vector3dVector(
                np.tile(color, (len(cluster.points), 1))
            )
            clusters.append(cluster)

        print(f"[SceneMap] accepted {len(clusters)} navigable cluster(s)")
        return clusters
