"""ESDF-based 2D trajectory smoothing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize


@dataclass
class ESDFContext:
    esdf_map: np.ndarray
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    resolution: float
    clearance: float


def _bilinear_esdf_lookup(point: np.ndarray, ctx: ESDFContext) -> tuple[float, np.ndarray]:
    xi = int(np.floor((point[0] - ctx.x_min) / ctx.resolution))
    yi = int(np.floor((point[1] - ctx.y_min) / ctx.resolution))
    if not (0 < xi < ctx.esdf_map.shape[0] - 1 and 0 < yi < ctx.esdf_map.shape[1] - 1):
        return ctx.clearance, np.zeros(2)

    fx = (point[0] - (ctx.x_min + ctx.resolution * xi)) / ctx.resolution
    fy = (point[1] - (ctx.y_min + ctx.resolution * yi)) / ctx.resolution
    v00 = ctx.esdf_map[xi, yi]
    v10 = ctx.esdf_map[xi + 1, yi]
    v01 = ctx.esdf_map[xi, yi + 1]
    v11 = ctx.esdf_map[xi + 1, yi + 1]

    dist = (1 - fx) * ((1 - fy) * v00 + fy * v01) + fx * ((1 - fy) * v10 + fy * v11)
    grad_x = ((1 - fy) * (v10 - v00) + fy * (v11 - v01)) / ctx.resolution
    grad_y = ((1 - fx) * (v01 - v00) + fx * (v11 - v10)) / ctx.resolution
    return float(dist), np.array([grad_x, grad_y])


def _obstacle_cost(traj: np.ndarray, ctx: ESDFContext) -> float:
    cost = 0.0
    for point in traj:
        dist, _ = _bilinear_esdf_lookup(point, ctx)
        if dist < ctx.clearance:
            cost += (ctx.clearance - dist) ** 2
    return float(cost)


def _smoothness_cost(traj: np.ndarray) -> float:
    d2x = np.diff(traj[:, 0], 2)
    d2y = np.diff(traj[:, 1], 2)
    return float(np.sum(d2x ** 2 + d2y ** 2))


def _objective(flat: np.ndarray, ctx: ESDFContext, lambda_smooth: float) -> float:
    traj = flat.reshape(-1, 2)
    return _obstacle_cost(traj, ctx) + lambda_smooth * _smoothness_cost(traj)


def _gradient(flat: np.ndarray, ctx: ESDFContext, lambda_smooth: float) -> np.ndarray:
    traj = flat.reshape(-1, 2)
    grad = np.zeros_like(traj)
    n = traj.shape[0]

    for i in range(1, n - 1):
        dist, dist_grad = _bilinear_esdf_lookup(traj[i], ctx)
        if dist < ctx.clearance:
            grad[i] -= 2.0 * (ctx.clearance - dist) * dist_grad

    if n > 2:
        d2x = np.diff(traj[:, 0], 2)
        d2y = np.diff(traj[:, 1], 2)
        for i in range(1, n - 1):
            grad[i, 0] += lambda_smooth * (-4.0 * d2x[i - 1])
            grad[i, 1] += lambda_smooth * (-4.0 * d2y[i - 1])
    return grad.ravel()


def _check_connectivity(traj: np.ndarray, ctx: ESDFContext) -> bool:
    for start, end in zip(traj[:-1], traj[1:]):
        segment = end - start
        length = np.linalg.norm(segment)
        n_samples = max(10, int(length / ctx.resolution * 2))
        for idx in range(n_samples):
            t = idx / (n_samples - 1)
            point = start + t * segment
            xi = int(np.floor((point[0] - ctx.x_min) / ctx.resolution))
            yi = int(np.floor((point[1] - ctx.y_min) / ctx.resolution))
            if not (0 <= xi < ctx.esdf_map.shape[0] and 0 <= yi < ctx.esdf_map.shape[1]):
                return False
            if ctx.esdf_map[xi, yi] < 0:
                return False
    return True


def optimize_trajectory(
    initial_traj: np.ndarray,
    esdf_map: np.ndarray,
    lambda_smooth: float,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    resolution: float,
    clearance: float = 0.5,
) -> np.ndarray:
    ctx = ESDFContext(esdf_map, x_min, x_max, y_min, y_max, resolution, clearance)
    if not _check_connectivity(initial_traj, ctx):
        return initial_traj

    result = minimize(
        _objective,
        initial_traj.ravel(),
        args=(ctx, lambda_smooth),
        method="L-BFGS-B",
        jac=_gradient,
    )
    optimized = result.x.reshape(-1, 2)
    return optimized if _check_connectivity(optimized, ctx) else initial_traj
