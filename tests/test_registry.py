from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from bci.models.base import BaseDecoder
from bci.models.registry import build, list_available, register


class _DummyDecoder(BaseDecoder):
    def __init__(self, n_classes: int = 2) -> None:
        self.n_classes = n_classes

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseDecoder":
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.zeros(len(X), dtype=int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        n = len(X)
        p = np.full((n, self.n_classes), 1.0 / self.n_classes)
        return p

    def get_params(self) -> dict[str, Any]:
        return {"n_classes": self.n_classes}

    def set_params(self, params: dict[str, Any]) -> None:
        self.n_classes = params["n_classes"]


def test_register_and_build() -> None:
    register("dummy_for_test")(_DummyDecoder)
    assert "dummy_for_test" in list_available()

    dec = build("dummy_for_test", n_classes=3)
    assert isinstance(dec, _DummyDecoder)
    assert dec.n_classes == 3

    proba = dec.predict_proba(np.zeros((5, 2, 10)))
    assert proba.shape == (5, 3)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_build_unknown_raises() -> None:
    with pytest.raises(KeyError):
        build("does_not_exist")


def test_register_non_decoder_raises() -> None:
    with pytest.raises(TypeError):

        @register("bad")
        class NotADecoder:  # noqa: D401
            pass
