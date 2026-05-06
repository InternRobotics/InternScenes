"""Filesystem helpers for locating USD scene assets."""

from __future__ import annotations

from pathlib import Path


def find_single_usd(scene_dir: str | Path) -> tuple[str | None, list[str]]:
    """Return the only direct USD file in a scene directory.

    Release scene directories are expected to contain exactly one ``.usd`` file.
    The helper is intentionally strict so malformed scene packages are not
    rendered or parsed with an arbitrary file.
    """
    usd_files = sorted(
        (path for path in Path(scene_dir).glob("*.usd") if path.is_file()),
        key=lambda path: path.name,
    )
    usd_paths = [str(path) for path in usd_files]
    if len(usd_paths) == 1:
        return usd_paths[0], usd_paths
    return None, usd_paths
