"""Base interface for trajectory strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from ..scene_map import SceneMap


@dataclass
class StrategyResult:
    waypoints: np.ndarray
    metadata: dict = field(default_factory=dict)
    failure_reason: str = ""


class BaseStrategy(ABC):
    def __init__(self, params: dict | None = None) -> None:
        self.params = params or {}

    @abstractmethod
    def generate(self, scene_map: SceneMap) -> tuple[bool, StrategyResult]:
        """Generate 2D waypoints on a built SceneMap."""
