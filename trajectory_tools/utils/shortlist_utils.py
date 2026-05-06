"""Read optional scene shortlist CSV files."""

from __future__ import annotations

import csv


def load_shortlist_scenes(
    csv_path: str,
    usd_id: int,
    min_rating: int = 3,
) -> list[str]:
    scenes = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            if int(row["usd_id"]) == usd_id and int(row["rating"]) >= min_rating:
                scenes.append(row["scene_id"])
    return scenes
