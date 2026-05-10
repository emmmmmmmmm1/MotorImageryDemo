from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseDecoder(ABC):
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseDecoder": ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray: ...

    @abstractmethod
    def get_params(self) -> dict[str, Any]: ...

    @abstractmethod
    def set_params(self, params: dict[str, Any]) -> None: ...
