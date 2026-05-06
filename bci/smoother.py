from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseSmoother(ABC):
    @abstractmethod
    def update(self, proba: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def get_params(self) -> dict[str, Any]: ...


class PassthroughSmoother(BaseSmoother):
    """Returns probabilities unchanged. Useful before EMA is wired in."""

    def update(self, proba: np.ndarray) -> np.ndarray:
        return np.asarray(proba)

    def reset(self) -> None:
        return None

    def get_params(self) -> dict[str, Any]:
        return {}


_SMOOTHERS: dict[str, type[BaseSmoother]] = {
    "passthrough": PassthroughSmoother,
}


def make_smoother(name: str, params: dict[str, Any] | None = None) -> BaseSmoother:
    if name not in _SMOOTHERS:
        raise KeyError(
            f"unknown smoother {name!r}; available: {sorted(_SMOOTHERS)}"
        )
    return _SMOOTHERS[name](**(params or {}))
