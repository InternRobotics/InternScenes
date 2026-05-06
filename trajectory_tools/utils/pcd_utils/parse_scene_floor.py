"""Floor-height extraction from scene point clouds and USD floor prim metadata."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from sklearn.cluster import DBSCAN

from utils.usd_utils.converters import sample_points_from_prim
from utils.usd_utils.prim_utils import compute_bbox


def _extract_main_bins(z_hist: tuple[np.ndarray, np.ndarray], window_size: int = 5) -> tuple[np.ndarray, np.ndarray]:
    data, bins = z_hist
    kernel = np.ones(window_size) / window_size
    window_avg = np.convolve(data, kernel, mode="valid")
    mean, std = np.mean(data), np.std(data)
    threshold = mean - 0.5 * std if mean - 0.5 * std > 0 else mean

    left = 0
    for idx, value in enumerate(window_avg):
        if value > threshold:
            left = idx if idx > 0 else 0
            break

    right = len(data) - 1
    for idx in range(len(window_avg) - 1, -1, -1):
        if window_avg[idx] > threshold:
            right = min(idx + window_size - 1, len(data) - 1)
            break

    return data[left:right + 1], bins[left:right + 2]


def _scene_z_histogram(scene_points: np.ndarray, resolution: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
    z_coords = scene_points[:, 2]
    bin_count = max(int(abs(np.max(z_coords) - np.min(z_coords)) / resolution), 1)
    return _extract_main_bins(np.histogram(z_coords, bins=bin_count))


def _peak_indices(z_smooth: np.ndarray, min_peak_height: float, resolution: float = 0.01) -> np.ndarray:
    distance = 0.2 / resolution
    peaks, _ = find_peaks(z_smooth, distance=distance, height=min_peak_height)
    if len(z_smooth) >= 2:
        if z_smooth[0] > z_smooth[1]:
            peaks = np.append(peaks, 0)
        if z_smooth[-1] > z_smooth[-2]:
            peaks = np.append(peaks, len(z_smooth) - 1)
    return np.unique(peaks)


def _cluster_top_peaks(
    labels: np.ndarray,
    peaks_index: np.ndarray,
    z_histogram: tuple[np.ndarray, np.ndarray],
    z_smooth: np.ndarray,
) -> np.ndarray:
    clustered_peaks = []
    label_values = np.unique(labels)
    for idx, label in enumerate(label_values):
        peaks = peaks_index[labels == label]
        if idx == 0 or idx == len(label_values) - 1:
            top_peaks = peaks[np.argsort(z_smooth[peaks])[-1:]].tolist()
        else:
            top_peak = peaks[np.argsort(z_smooth[peaks])[-1]]
            top_peaks = [top_peak, top_peak]
        clustered_peaks.extend([z_histogram[1][peak] for peak in top_peaks])
    return np.sort(clustered_peaks)


def extract_floor_heights(scene_pcd_points: np.ndarray) -> list[list[float]]:
    z_histogram = _scene_z_histogram(scene_pcd_points)
    z_smooth = gaussian_filter1d(z_histogram[0], sigma=1)
    min_peak_height = np.percentile(z_smooth, 95)
    peaks_index = _peak_indices(z_smooth, min_peak_height)

    peak_locations = z_histogram[1][peaks_index]
    labels = DBSCAN(eps=1, min_samples=1).fit(peak_locations.reshape(-1, 1)).labels_
    clustered_peaks = _cluster_top_peaks(labels, peaks_index, z_histogram, z_smooth)

    floors = []
    for idx in range(0, len(clustered_peaks) - 1, 2):
        floors.append([float(clustered_peaks[idx]), float(clustered_peaks[idx + 1])])
    print(f"[FloorParser] Floor levels: {floors}")
    return floors


def _extract_floor_metadata(mesh_prims: list, meters_per_unit: float) -> list[dict]:
    metadata = []
    for prim in mesh_prims:
        try:
            bbox = compute_bbox(prim) * meters_per_unit
        except Exception:
            continue
        z_min = float(bbox[0, 2])
        z_max = float(bbox[1, 2])
        entry = {
            "name": prim.GetName(),
            "path": str(prim.GetPath()),
            "z_min": z_min,
            "z_max": z_max,
            "points": None,
        }
        if 0.0 < (z_max - z_min) <= 0.5:
            try:
                points, mesh = sample_points_from_prim(prim, num_points=1000)
                del mesh
                entry["points"] = points * meters_per_unit
            except Exception:
                pass
        metadata.append(entry)
    return metadata


def fix_floor_height_from_metadata(floor_height: float, prim_metadata: list[dict]) -> float:
    floor_height = round(float(floor_height), 5)
    candidates = []
    for entry in prim_metadata:
        z_min, z_max = entry["z_min"], entry["z_max"]
        inside_range = (
            (floor_height <= z_max or np.isclose(floor_height, z_max, atol=0.01))
            and (floor_height >= z_min or np.isclose(floor_height, z_min, atol=0.01))
        )
        if inside_range and z_max - z_min <= 0.5:
            candidates.append(entry)

    if not candidates:
        return floor_height

    best = sorted(candidates, key=lambda item: item["z_max"])[0]
    if best["points"] is None:
        return floor_height

    z_values = best["points"][:, 2]
    hist, bin_edges = np.histogram(z_values, bins=100)
    valid_indices = [idx for idx in np.argsort(hist)[::-1] if hist[idx] > 100][:2]
    if not valid_indices:
        return floor_height

    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    corrected = float(np.max(bin_centers[valid_indices]))
    return floor_height if np.isclose(corrected, floor_height, atol=0.01) else corrected
