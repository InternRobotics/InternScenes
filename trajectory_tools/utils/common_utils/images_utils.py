"""Image helpers for render outputs."""

from __future__ import annotations

import numpy as np


def _instance_color(instance_id: int) -> np.ndarray:
    rng = np.random.default_rng(instance_id if instance_id >= 0 else abs(instance_id) + 10000)
    return rng.integers(0, 256, size=3, dtype=np.uint8)


def colorize_instances(mask: np.ndarray, colors: list | None = None) -> np.ndarray:
    h, w = mask.shape
    color_mask = np.zeros((h, w, 3), dtype=np.uint8)
    instance_ids = np.unique(mask)
    for instance_id in instance_ids:
        if instance_id == 0:
            continue
        if colors is not None and 0 <= instance_id < len(colors):
            color = colors[instance_id]
        else:
            color = _instance_color(int(instance_id))
        color_mask[mask == instance_id] = color
    return color_mask
