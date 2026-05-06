"""Geometry helpers used by trajectory generation."""

from __future__ import annotations

import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree


def numpy_2d_distance(points_a: np.ndarray, points_b: np.ndarray) -> np.ndarray:
    tree = cKDTree(points_b[:, :2])
    return tree.query(points_a[:, :2], k=1)[0]


def pointcloud_2d_distance(
    pcd_a: o3d.geometry.PointCloud,
    pcd_b: o3d.geometry.PointCloud,
) -> np.ndarray:
    return numpy_2d_distance(np.asarray(pcd_a.points), np.asarray(pcd_b.points))


def points_2d_distance(points_a: np.ndarray, points_b: np.ndarray) -> np.ndarray:
    return numpy_2d_distance(points_a, points_b)


def clockwise_angle(v1: np.ndarray, v2: np.ndarray) -> float:
    dot = float(np.dot(v1, v2))
    det = float(v1[0] * v2[1] - v1[1] * v2[0])
    return float(np.arctan2(det, dot))
