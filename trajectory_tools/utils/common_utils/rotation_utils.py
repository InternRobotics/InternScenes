"""Rotation conversion helpers."""

from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation


def euler_angles_to_quats(
    euler_angles: np.ndarray,
    degrees: bool = False,
    extrinsic: bool = True,
) -> np.ndarray:
    order = "xyz" if extrinsic else "XYZ"
    result = Rotation.from_euler(order, euler_angles, degrees=degrees).as_quat()
    if len(result.shape) == 1:
        return result[[3, 0, 1, 2]]
    return result[:, [3, 0, 1, 2]]
