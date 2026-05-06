from __future__ import annotations

import numpy as np
from scipy.signal import welch

from tests._synth import generate_synthetic_mi


def _band_power(x: np.ndarray, fs: float, lo: float, hi: float) -> float:
    f, p = welch(x, fs=fs, nperseg=min(len(x), int(fs * 2)))
    mask = (f >= lo) & (f <= hi)
    return float(np.trapezoid(p[mask], f[mask]))


def test_shape_and_labels_2ch() -> None:
    X, y = generate_synthetic_mi(n_trials_per_class=20, n_channels=2, seed=0)
    assert X.shape == (40, 2, 512)
    assert y.shape == (40,)
    assert set(np.unique(y).tolist()) == {0, 1}
    assert (y == 0).sum() == 20
    assert (y == 1).sum() == 20


def test_shape_14ch() -> None:
    X, _ = generate_synthetic_mi(n_trials_per_class=20, n_channels=14, seed=0)
    assert X.shape == (40, 14, 512)


def test_class_specific_mu_pattern_2ch() -> None:
    X, y = generate_synthetic_mi(n_trials_per_class=30, n_channels=2, seed=1)
    fs = 128.0
    left = X[y == 0]
    right = X[y == 1]
    # left class: ch0 (C3) high mu, ch1 (C4) low mu
    p_c3_left = np.mean([_band_power(t[0], fs, 8, 13) for t in left])
    p_c4_left = np.mean([_band_power(t[1], fs, 8, 13) for t in left])
    p_c3_right = np.mean([_band_power(t[0], fs, 8, 13) for t in right])
    p_c4_right = np.mean([_band_power(t[1], fs, 8, 13) for t in right])

    assert p_c3_left > p_c4_left
    assert p_c4_right > p_c3_right
    # Cross-class: left/right swap on each channel
    assert p_c3_left > p_c3_right
    assert p_c4_right > p_c4_left


def test_seed_is_deterministic() -> None:
    X1, y1 = generate_synthetic_mi(seed=42)
    X2, y2 = generate_synthetic_mi(seed=42)
    np.testing.assert_array_equal(X1, X2)
    np.testing.assert_array_equal(y1, y2)
