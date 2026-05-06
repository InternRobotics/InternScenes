"""BBox-based scene prim noise filtering."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import label

from utils.usd_utils.prim_utils import compute_bbox


def classify_prims_by_bbox(
    mesh_prims: list,
    meters_per_unit: float,
    grid_resolution: float = 0.1,
    majority_threshold: float = 0.5,
) -> dict[str, float]:
    def classify_plane(axis_pair: tuple[int, int]) -> dict[str, float]:
        a0, a1 = axis_pair
        bboxes = []
        for prim in mesh_prims:
            try:
                bbox = compute_bbox(prim) * meters_per_unit
                values = (
                    float(bbox[0, a0]),
                    float(bbox[1, a0]),
                    float(bbox[0, a1]),
                    float(bbox[1, a1]),
                )
                bboxes.append(None if any(np.isnan(value) for value in values) else values)
            except Exception:
                bboxes.append(None)

        valid_bboxes = [bbox for bbox in bboxes if bbox is not None]
        if not valid_bboxes:
            return {str(prim.GetPath()): 1.0 for prim in mesh_prims}

        g0_min = min(bbox[0] for bbox in valid_bboxes)
        g0_max = max(bbox[1] for bbox in valid_bboxes)
        g1_min = min(bbox[2] for bbox in valid_bboxes)
        g1_max = max(bbox[3] for bbox in valid_bboxes)
        edge0 = np.arange(g0_min, g0_max + grid_resolution, grid_resolution)
        edge1 = np.arange(g1_min, g1_max + grid_resolution, grid_resolution)
        n0, n1 = len(edge0) - 1, len(edge1) - 1
        if n0 <= 0 or n1 <= 0:
            return {str(prim.GetPath()): 1.0 for prim in mesh_prims}

        density = np.zeros((n0, n1), dtype=np.int32)
        for bbox in valid_bboxes:
            a0_min, a0_max, a1_min, a1_max = bbox
            i_min = max(0, int((a0_min - g0_min) / grid_resolution))
            i_max = min(n0, int((a0_max - g0_min) / grid_resolution) + 1)
            j_min = max(0, int((a1_min - g1_min) / grid_resolution))
            j_max = min(n1, int((a1_max - g1_min) / grid_resolution) + 1)
            if i_max > i_min and j_max > j_min:
                density[i_min:i_max, j_min:j_max] += 1

        labeled, num_features = label(density > 0)
        if num_features == 0:
            return {str(prim.GetPath()): 1.0 for prim in mesh_prims}

        cluster_labels = labeled.ravel()
        cell_counts = np.bincount(cluster_labels, minlength=num_features + 1)[1:]
        areas = cell_counts * (grid_resolution ** 2)
        overlap = np.zeros(num_features, dtype=np.float64)
        for cluster_idx in range(num_features):
            overlap[cluster_idx] = density[labeled == cluster_idx + 1].sum()

        densities = overlap / (areas + 1e-6)
        scores = (
            0.5 * (overlap / (overlap.max() or 1))
            + 0.3 * (areas / (areas.max() or 1))
            + 0.2 * (densities / (densities.max() or 1))
        )
        main_label = int(np.argmax(scores)) + 1

        survival = {}
        for prim, bbox in zip(mesh_prims, bboxes):
            path = str(prim.GetPath())
            if bbox is None:
                survival[path] = 1.0
                continue
            a0_min, a0_max, a1_min, a1_max = bbox
            i_min = max(0, int((a0_min - g0_min) / grid_resolution))
            i_max = min(n0, int((a0_max - g0_min) / grid_resolution) + 1)
            j_min = max(0, int((a1_min - g1_min) / grid_resolution))
            j_max = min(n1, int((a1_max - g1_min) / grid_resolution) + 1)
            if i_max <= i_min or j_max <= j_min:
                survival[path] = 1.0
                continue
            sub = labeled[i_min:i_max, j_min:j_max]
            fraction = float((sub == main_label).sum()) / sub.size
            survival[path] = 1.0 if fraction >= majority_threshold else 0.0
        return survival

    xy_survival = classify_plane((0, 1))
    xz_survival = classify_plane((0, 2))
    final = {}
    for prim in mesh_prims:
        path = str(prim.GetPath())
        final[path] = xy_survival[path] * xz_survival[path]
    return final
