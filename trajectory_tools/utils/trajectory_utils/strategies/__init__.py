"""Trajectory strategy registry."""

from __future__ import annotations

from typing import Callable

from .base_strategy import BaseStrategy

_REGISTRY: dict[str, type[BaseStrategy]] = {}


def register_strategy(name: str) -> Callable:
    def wrap(cls: type[BaseStrategy]) -> type[BaseStrategy]:
        if name in _REGISTRY:
            raise ValueError(f"Strategy already registered: {name}")
        _REGISTRY[name] = cls
        return cls
    return wrap


def create_strategy(name: str, params: dict | None = None) -> BaseStrategy:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy '{name}'. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name](params)


from . import astar_strategy  # noqa: E402,F401
from . import forward_motion_strategy  # noqa: E402,F401
