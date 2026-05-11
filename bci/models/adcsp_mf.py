from __future__ import annotations

import sys
from typing import Any, Iterable
from pathlib import Path

import numpy as np

from pyriemann.estimation import Covariances
from sklearn.pipeline import make_pipeline

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from bci.models.base import BaseDecoder
    from bci.models.registry import register
else:
    from .base import BaseDecoder
    from .registry import register

try:
    from mfacc import MFACC, ADCSP
except Exception:  # pragma: no cover - optional dependency
    MFACC = None  # type: ignore
    ADCSP = None  # type: ignore


'''
Adaptive Common Spatial Pattern (ACSP) + Means Field Accumulator (MFACC)
decoder for motor imagery BCI.
'''

@register("adcsp_mf")
class ADCSPMFDecoder(BaseDecoder):

    def __init__(
        self,
        cov_estimator: str = "oas", # algorithm for covariance estimation (e.g. "oas", "lwf", "scm")
        adcsp_modes: Iterable[str] | None = None, # list of ADCSP modes to apply (e.g. ["high_electrodes_count", "low_electrodes_count"])
        mfacc_kwargs: dict[str, Any] | None = None, # keyword arguments for MFACC (e.g. {"method_label": "lda", "n_jobs": 1, "rpme_enabled": False})
    ) -> None:
        self.cov_estimator = cov_estimator
        self.adcsp_modes = (
            tuple(adcsp_modes) if adcsp_modes is not None else ("high_electrodes_count",)
        )
        self.mfacc_kwargs = dict(
            mfacc_kwargs or {"method_label": "lda", "n_jobs": 1, "rpme_enabled": False}
        )
        self.pipeline = None
        self.classes_ = None

    # internal method to build the sklearn pipeline based on current parameters
    def _build_pipeline(self):
        if MFACC is None or ADCSP is None:  # pragma: no cover - runtime error if missing
            raise RuntimeError("mfacc package is required for ADCSP+MF decoder")
        steps = [Covariances(estimator=self.cov_estimator)] # add covariance estimation step
        for mode in self.adcsp_modes: # add ADCSP stages for each specified mode
            steps.append(ADCSP(mode=mode))
        steps.append(MFACC(**self.mfacc_kwargs)) # add final MFACC classifier stage
        return make_pipeline(*steps)

    # fit the model to training data
    def fit(self, X: np.ndarray, y: np.ndarray) -> "ADCSPMFDecoder":
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_channels, n_samples); got shape {X.shape}"
            )
        pipe = self._build_pipeline()
        pipe.fit(X.astype(np.float64), y) # fit the pipeline (many pyriemann/mfacc components expect float64)
        self.pipeline = pipe
        try:
            final = pipe[-1] # capture classes from final estimator if available
            self.classes_ = getattr(final, "classes_", None) # capture classes from final estimator if available
        except Exception:
            self.classes_ = None
        return self
    
    # predict class labels for new data
    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("ADCSPMFDecoder.fit must be called before predict.")
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_channels, n_samples); got shape {X.shape}"
            )
        return np.asarray(self.pipeline.predict(X.astype(np.float64)))
    
    # predict class probabilities for new data. If the final estimator does not
    # support predict_proba, fallback to one-hot encoding of predictions.
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.pipeline is None:
            raise RuntimeError("ADCSPMFDecoder.fit must be called before predict_proba.")
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_channels, n_samples); got shape {X.shape}"
            )
        final = self.pipeline[-1]
        if hasattr(final, "predict_proba"):
            return np.asarray(self.pipeline.predict_proba(X.astype(np.float64)))
        # fallback: one-hot encode predictions when estimator has no predict_proba
        preds = self.pipeline.predict(X.astype(np.float64))
        classes = self.classes_ if self.classes_ is not None else np.unique(preds)
        proba = np.zeros((len(preds), len(classes)), dtype=np.float64)
        for i, p in enumerate(preds):
            idx = int(np.where(classes == p)[0][0])
            proba[i, idx] = 1.0
        return proba
    
    # get current parameters as a dictionary
    def get_params(self) -> dict[str, Any]:
        return {
            "cov_estimator": self.cov_estimator,
            "adcsp_modes": list(self.adcsp_modes),
            "mfacc_kwargs": dict(self.mfacc_kwargs),
        }
    
    # set parameters from a dictionary and reset pipeline and classes
    def set_params(self, params: dict[str, Any]) -> None:
        if "cov_estimator" in params:
            self.cov_estimator = params["cov_estimator"]
        if "adcsp_modes" in params:
            self.adcsp_modes = tuple(params["adcsp_modes"])
        if "mfacc_kwargs" in params:
            self.mfacc_kwargs = dict(params["mfacc_kwargs"])
        self.pipeline = None
        self.classes_ = None
