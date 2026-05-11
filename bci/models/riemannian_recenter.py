from __future__ import annotations

import sys
from typing import Any
from pathlib import Path

import numpy as np

from pyriemann.classification import MDM
from pyriemann.estimation import Covariances
from pyriemann.utils.base import invsqrtm
from pyriemann.utils.mean import mean_covariance

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from bci.models.base import BaseDecoder
    from bci.models.registry import register
else:
    from .base import BaseDecoder
    from .registry import register


@register("riemannian_recenter")
class RiemannianRecenterDecoder(BaseDecoder):
    """Riemannian MDM with per-subject recentering for cross-subject transfer.

    Two-phase workflow
    ------------------
    1. Offline — fit_source_subjects(Xs, ys):
       For each source subject, compute the Riemannian mean of their covariance
       matrices and recenter to the identity (M^-½ C M^-½).  All recentered
       covariances are pooled and a shared MDM classifier is trained.

    2. Calibration — fit(X_calib, y_calib):
       Estimate the new subject's Riemannian mean from a handful of calibration
       trials and store it as the recentering reference.  Inference then maps
       each incoming window into the same space as the source data.

    References
    ----------
    Zanini et al. (2018). Transfer Learning: A Riemannian Geometry Framework
    With Applications to Brain-Computer Interfaces.
    IEEE Trans Biomed Eng 65(5):1107-1116. DOI:10.1109/TBME.2017.2742501
    """

    def __init__(self, metric: str = "riemann", n_jobs: int = 1) -> None:
        self.metric = metric
        self.n_jobs = n_jobs
        self.mdm_: MDM | None = None
        self.classes_: np.ndarray | None = None
        self.M_recenter_: np.ndarray | None = None  # (n_ch, n_ch) new-subject mean

    # ------------------------------------------------------------------
    # Offline multi-subject pre-training
    # ------------------------------------------------------------------

    def fit_source_subjects(
        self,
        Xs: list[np.ndarray],
        ys: list[np.ndarray],
    ) -> "RiemannianRecenterDecoder":
        """Pre-train MDM on pooled recentered covariances from source subjects.

        Parameters
        ----------
        Xs : list of (n_trials, n_ch, n_samples) float64 arrays, one per subject.
        ys : list of (n_trials,) integer label arrays, one per subject.
        """
        cov_est = Covariances(estimator="oas")
        all_C: list[np.ndarray] = []
        all_y: list[np.ndarray] = []

        for s, (X_s, y_s) in enumerate(zip(Xs, ys)):
            if X_s.ndim != 3:
                raise ValueError(
                    f"Xs[{s}] must be (n_trials, n_ch, n_samples); got shape {X_s.shape}"
                )
            C_s = cov_est.transform(X_s.astype(np.float64))
            M_s = mean_covariance(C_s, metric=self.metric)
            M_s_invsqrt = invsqrtm(M_s)
            # Recenter: maps M_s → identity on the SPD manifold
            C_s_rec = M_s_invsqrt[np.newaxis] @ C_s @ M_s_invsqrt[np.newaxis]
            all_C.append(C_s_rec)
            all_y.append(y_s)

        C_pool = np.concatenate(all_C, axis=0)
        y_pool = np.concatenate(all_y, axis=0)

        self.mdm_ = MDM(metric=self.metric, n_jobs=self.n_jobs)
        self.mdm_.fit(C_pool, y_pool)
        self.classes_ = np.asarray(self.mdm_.classes_)
        return self

    # ------------------------------------------------------------------
    # BaseDecoder interface — calibration for a new subject
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RiemannianRecenterDecoder":
        """Compute the recentering reference from new-subject calibration data.

        Labels are only used when no source model exists (standalone mode).
        The recentering itself is unsupervised — only X is needed to estimate
        the subject's Riemannian mean.
        """
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_ch, n_samples); got shape {X.shape}"
            )
        cov_est = Covariances(estimator="oas")
        C_calib = cov_est.transform(X.astype(np.float64))
        self.M_recenter_ = mean_covariance(C_calib, metric=self.metric)

        if self.mdm_ is None:
            # Standalone mode: train MDM directly on recentered calibration data
            M_invsqrt = invsqrtm(self.M_recenter_)
            C_rec = M_invsqrt[np.newaxis] @ C_calib @ M_invsqrt[np.newaxis]
            self.mdm_ = MDM(metric=self.metric, n_jobs=self.n_jobs)
            self.mdm_.fit(C_rec, y)
            self.classes_ = np.asarray(self.mdm_.classes_)
        return self

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _recenter(self, X: np.ndarray) -> np.ndarray:
        if self.M_recenter_ is None:
            raise RuntimeError(
                "Call fit() to compute the recentering reference before inference."
            )
        cov_est = Covariances(estimator="oas")
        C = cov_est.transform(X.astype(np.float64))
        M_invsqrt = invsqrtm(self.M_recenter_)
        return M_invsqrt[np.newaxis] @ C @ M_invsqrt[np.newaxis]

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.mdm_ is None:
            raise RuntimeError(
                "Call fit_source_subjects() and fit() before predict()."
            )
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_ch, n_samples); got shape {X.shape}"
            )
        return np.asarray(self.mdm_.predict(self._recenter(X)))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self.mdm_ is None:
            raise RuntimeError(
                "Call fit_source_subjects() and fit() before predict_proba()."
            )
        if X.ndim != 3:
            raise ValueError(
                f"X must be (n_trials, n_ch, n_samples); got shape {X.shape}"
            )
        return np.asarray(self.mdm_.predict_proba(self._recenter(X)))

    # ------------------------------------------------------------------
    # Param interface
    # ------------------------------------------------------------------

    def get_params(self) -> dict[str, Any]:
        return {"metric": self.metric, "n_jobs": self.n_jobs}

    def set_params(self, params: dict[str, Any]) -> None:
        if "metric" in params:
            self.metric = params["metric"]
        if "n_jobs" in params:
            self.n_jobs = params["n_jobs"]
        self.mdm_ = None
        self.M_recenter_ = None
        self.classes_ = None
