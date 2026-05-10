from __future__ import annotations

from typing import Any

import numpy as np
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from .base import BaseDecoder
from .registry import register


@register("csp_lda")
class CSPLDADecoder(BaseDecoder):
    def __init__(
        self,
        n_components: int = 4,
        reg: str | float | None = None,
        log: bool = True,
    ) -> None:
        self.n_components_cfg = int(n_components)
        self.reg = reg
        self.log = log
        self.csp: CSP | None = None
        self.lda: LinearDiscriminantAnalysis | None = None
        self.classes_: np.ndarray | None = None
        self.n_components_used_: int | None = None

    def _resolved_n_components(self, n_channels: int) -> int:
        return max(1, min(self.n_components_cfg, n_channels))

    def fit(self, X: np.ndarray, y: np.ndarray) -> "CSPLDADecoder":
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_channels, n_samples); got shape {X.shape}"
            )
        n_channels = X.shape[1]
        n_comp = self._resolved_n_components(n_channels)
        self.csp = CSP(
            n_components=n_comp,
            reg=self.reg,
            log=self.log,
            transform_into="average_power",
        )
        # MNE CSP expects float64
        self.csp.fit(X.astype(np.float64), y)
        feats = self.csp.transform(X.astype(np.float64))

        self.lda = LinearDiscriminantAnalysis()
        self.lda.fit(feats, y)
        self.classes_ = self.lda.classes_
        self.n_components_used_ = n_comp
        return self

    def _features(self, X: np.ndarray) -> np.ndarray:
        if self.csp is None:
            raise RuntimeError("CSPLDADecoder.fit must be called before transform.")
        return self.csp.transform(X.astype(np.float64))

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.lda is None:
            raise RuntimeError("CSPLDADecoder.fit must be called before predict.")
        return self.lda.predict(self._features(X))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.lda is None:
            raise RuntimeError(
                "CSPLDADecoder.fit must be called before predict_proba."
            )
        return self.lda.predict_proba(self._features(X))

    def get_params(self) -> dict[str, Any]:
        return {
            "n_components": self.n_components_cfg,
            "reg": self.reg,
            "log": self.log,
        }

    def set_params(self, params: dict[str, Any]) -> None:
        if "n_components" in params:
            self.n_components_cfg = int(params["n_components"])
        if "reg" in params:
            self.reg = params["reg"]
        if "log" in params:
            self.log = bool(params["log"])
