from __future__ import annotations

import numpy as np

from bci.config import PreprocessingConfig
from bci.models.csp_lda import CSPLDADecoder
from bci.pipeline import InferencePipeline
from bci.preprocessing import Preprocessor
from bci.smoother import PassthroughSmoother
from tests._synth import generate_synthetic_mi


def _fitted_pipeline() -> InferencePipeline:
    X, y = generate_synthetic_mi(n_trials_per_class=20, n_channels=2, seed=0)
    cfg = PreprocessingConfig(fs=128.0, channel_order=["C3", "C4"])
    pre = Preprocessor(cfg)
    decoder = CSPLDADecoder(n_components=4).fit(X, y)
    return InferencePipeline(pre, decoder, PassthroughSmoother())


def test_predict_window_shape_2d_input() -> None:
    pipe = _fitted_pipeline()
    window = np.random.default_rng(0).standard_normal((2, 256)).astype(np.float32)
    proba = pipe.predict_window(window)
    assert proba.shape == (2,)
    assert np.isclose(proba.sum(), 1.0, atol=1e-6)


def test_predict_window_accepts_3d_singleton() -> None:
    pipe = _fitted_pipeline()
    window = np.random.default_rng(1).standard_normal((1, 2, 256)).astype(np.float32)
    proba = pipe.predict_window(window)
    assert proba.shape == (2,)


def test_predict_window_rejects_batch() -> None:
    pipe = _fitted_pipeline()
    bad = np.zeros((3, 2, 256))
    try:
        pipe.predict_window(bad)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for batched input")


def test_passthrough_smoother_does_not_alter_proba() -> None:
    pipe = _fitted_pipeline()
    window = np.random.default_rng(2).standard_normal((2, 256)).astype(np.float32)
    raw_proba = pipe.decoder.predict_proba(window[None, ...])[0]
    smoothed = pipe.predict_window(window)
    np.testing.assert_array_equal(smoothed, raw_proba)


def test_reset_smoother_runs() -> None:
    pipe = _fitted_pipeline()
    pipe.reset_smoother()  # Should not raise.
