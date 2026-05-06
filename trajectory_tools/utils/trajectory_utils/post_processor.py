"""Convert 2D waypoints into camera pose JSON."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.interpolate import make_interp_spline

from .geometry_tools import clockwise_angle
from utils.common_utils.rotation_utils import euler_angles_to_quats


@dataclass
class PostProcessConfig:
    min_step_distance: float = 0.3
    min_step_angle: float = 0.15
    min_turn_distance: float = 0.15
    pitch_rad: float = 0.0
    camera_height: float = 1.8
    bspline_degree: int = 3
    bspline_step: int = 100


@dataclass
class ProcessedTrajectory:
    points_3d: np.ndarray
    rotations_euler: np.ndarray
    camera_poses: list[Any]


class TrajectoryPostProcessor:
    def __init__(self, config: PostProcessConfig | None = None) -> None:
        self.config = config or PostProcessConfig()

    def process(
        self,
        waypoints_2d: np.ndarray,
        floor_height: float,
        mode: str = "standard",
    ) -> tuple[ProcessedTrajectory | None, str]:
        if len(waypoints_2d) < 3:
            return None, f"too few input waypoints: {len(waypoints_2d)}"

        if mode == "direct":
            final_points = waypoints_2d
            final_rotations = self._waypoint_rotation(final_points)
        else:
            dense_points = self._bspline_points(waypoints_2d)
            rotations = self._waypoint_rotation(dense_points)
            final_points, final_rotations = self._downsample_trajectory(
                dense_points,
                rotations,
            )

        if len(final_points) < 10:
            return None, f"too few output frames: {len(final_points)}"

        cfg = self.config
        abs_height = cfg.camera_height + floor_height
        points_3d = np.column_stack((
            final_points,
            np.full(len(final_points), abs_height),
        ))
        rotations_euler = np.column_stack((
            np.full(len(final_points), cfg.pitch_rad),
            np.zeros(len(final_points)),
            final_rotations,
        ))

        camera_poses = []
        for point, rotation in zip(points_3d, rotations_euler):
            euler = [rotation[1], rotation[0], rotation[2] + np.pi / 2]
            quat = euler_angles_to_quats(euler)
            camera_poses.append((point.tolist(), quat.tolist()))

        return ProcessedTrajectory(points_3d, rotations_euler, camera_poses), ""

    def _bspline_points(self, waypoints: np.ndarray) -> np.ndarray:
        cfg = self.config
        t = np.linspace(0, 1, len(waypoints))
        spline = make_interp_spline(t, waypoints, k=cfg.bspline_degree)
        t_fine = np.linspace(0, 1, len(waypoints) * cfg.bspline_step)
        return spline(t_fine)

    @staticmethod
    def _waypoint_rotation(waypoints: np.ndarray) -> np.ndarray:
        vectors = waypoints[1:, :2] - waypoints[:-1, :2]
        angles = [
            2 * np.pi - clockwise_angle(vector, np.array([0, 1]))
            for vector in vectors
        ]
        angles.append(angles[-1])
        return np.array(angles)

    def _downsample_trajectory(
        self,
        points: np.ndarray,
        rotations: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        cfg = self.config
        final_points = [points[0]]
        final_rotations = [rotations[0]]

        for point, rotation in zip(points[1:], rotations[1:]):
            distance = np.linalg.norm(point[:2] - final_points[-1][:2])
            if distance > cfg.min_step_distance:
                final_points.append(point)
                final_rotations.append(rotation)
                continue
            if distance < cfg.min_turn_distance:
                continue
            delta = abs(rotation - final_rotations[-1])
            if min(delta, 2 * np.pi - delta) > cfg.min_step_angle:
                final_points.append(point)
                final_rotations.append(rotation)

        return np.array(final_points), np.array(final_rotations)
