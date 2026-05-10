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


class EMASmoother(BaseSmoother):
    """Exponential moving average over class probabilities.

    state_t = alpha * proba_t + (1 - alpha) * state_{t-1}
    The first call initialises the running state from proba_t directly,
    so warm-up does not pull predictions toward 0.
    """

    def __init__(self, alpha: float = 0.3) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self.alpha = float(alpha)
        self._state: np.ndarray | None = None

    def update(self, proba: np.ndarray) -> np.ndarray:
        arr = np.asarray(proba, dtype=np.float64)
        if self._state is None:
            self._state = arr.copy()
        else:
            self._state = self.alpha * arr + (1.0 - self.alpha) * self._state
        return self._state.copy()

    def reset(self) -> None:
        self._state = None

    def get_params(self) -> dict[str, Any]:
        return {"alpha": self.alpha}


_SMOOTHERS: dict[str, type[BaseSmoother]] = {
    "passthrough": PassthroughSmoother,
    "ema": EMASmoother,
}


def make_smoother(name: str, params: dict[str, Any] | None = None) -> BaseSmoother:
    if name not in _SMOOTHERS:
        raise KeyError(
            f"unknown smoother {name!r}; available: {sorted(_SMOOTHERS)}"
        )
    return _SMOOTHERS[name](**(params or {}))
