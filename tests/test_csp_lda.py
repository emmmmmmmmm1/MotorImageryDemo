from __future__ import annotations

import numpy as np
from sklearn.model_selection import train_test_split

import bci.models  # noqa: F401  -- ensures decoders register
from bci.models.csp_lda import CSPLDADecoder
from bci.models.registry import build, list_available
from tests._synth import generate_synthetic_mi


def _holdout_acc(decoder, X, y, seed=0) -> float:
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.3, random_state=seed, stratify=y
    )
    decoder.fit(Xtr, ytr)
    return float((decoder.predict(Xte) == yte).mean())


def test_registry_has_csp_lda() -> None:
    assert "csp_lda" in list_available()
    dec = build("csp_lda", n_components=4)
    assert isinstance(dec, CSPLDADecoder)


def test_csp_lda_14ch_high_acc() -> None:
    X, y = generate_synthetic_mi(n_trials_per_class=40, n_channels=14, seed=0)
    dec = CSPLDADecoder(n_components=4)
    acc = _holdout_acc(dec, X, y, seed=0)
    assert acc > 0.8, f"14ch acc {acc:.3f} should exceed 0.8"
    assert dec.n_components_used_ == 4


def test_csp_lda_2ch_runs_and_meets_baseline() -> None:
    X, y = generate_synthetic_mi(n_trials_per_class=40, n_channels=2, seed=0)
    dec = CSPLDADecoder(n_components=4)
    acc = _holdout_acc(dec, X, y, seed=0)
    assert acc > 0.65, f"2ch acc {acc:.3f} should exceed 0.65"


def test_csp_lda_2ch_clips_n_components() -> None:
    X, y = generate_synthetic_mi(n_trials_per_class=20, n_channels=2, seed=0)
    dec = CSPLDADecoder(n_components=4)
    dec.fit(X, y)
    assert dec.n_components_used_ == 2
    assert dec.csp is not None and dec.csp.n_components == 2


def test_csp_lda_predict_proba_shape() -> None:
    X, y = generate_synthetic_mi(n_trials_per_class=20, n_channels=2, seed=0)
    dec = build("csp_lda", n_components=4)
    dec.fit(X, y)
    proba = dec.predict_proba(X[:5])
    assert proba.shape == (5, 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_csp_lda_get_set_params_round_trip() -> None:
    dec = CSPLDADecoder(n_components=4, reg=None, log=True)
    params = dec.get_params()
    assert params["n_components"] == 4
    dec.set_params({"n_components": 2})
    assert dec.get_params()["n_components"] == 2
