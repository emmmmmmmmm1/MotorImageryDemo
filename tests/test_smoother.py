from __future__ import annotations

import numpy as np
import pytest

from bci.smoother import EMASmoother, PassthroughSmoother, make_smoother


def test_ema_first_update_initialises_to_input() -> None:
    s = EMASmoother(alpha=0.3)
    p0 = np.array([0.7, 0.3])
    out = s.update(p0)
    np.testing.assert_allclose(out, p0)


def test_ema_recursion_matches_formula() -> None:
    alpha = 0.3
    s = EMASmoother(alpha=alpha)
    seq = [
        np.array([0.7, 0.3]),
        np.array([0.6, 0.4]),
        np.array([0.5, 0.5]),
        np.array([0.4, 0.6]),
    ]
    state = seq[0].copy()
    s.update(seq[0])
    for p in seq[1:]:
        state = alpha * p + (1 - alpha) * state
        out = s.update(p)
        np.testing.assert_allclose(out, state)


def test_ema_smooths_noisy_signal() -> None:
    rng = np.random.default_rng(0)
    s = EMASmoother(alpha=0.2)
    truth = np.array([0.7, 0.3])
    raw_std_sum = 0.0
    smoothed_history: list[np.ndarray] = []
    for _ in range(200):
        noisy = truth + rng.standard_normal(2) * 0.1
        raw_std_sum += float(noisy.std())
        smoothed_history.append(s.update(noisy))
    smoothed = np.stack(smoothed_history[20:])  # drop warm-up
    assert smoothed.std(axis=0).mean() < 0.05


def test_ema_reset_clears_state() -> None:
    s = EMASmoother(alpha=0.3)
    s.update(np.array([0.9, 0.1]))
    s.update(np.array([0.8, 0.2]))
    s.reset()
    assert s._state is None
    out = s.update(np.array([0.5, 0.5]))
    np.testing.assert_allclose(out, [0.5, 0.5])


def test_ema_invalid_alpha_raises() -> None:
    with pytest.raises(ValueError):
        EMASmoother(alpha=0.0)
    with pytest.raises(ValueError):
        EMASmoother(alpha=1.5)


def test_ema_get_params() -> None:
    s = EMASmoother(alpha=0.25)
    assert s.get_params() == {"alpha": 0.25}


def test_make_smoother_factory_supports_ema_and_passthrough() -> None:
    e = make_smoother("ema", {"alpha": 0.5})
    assert isinstance(e, EMASmoother)
    assert e.alpha == 0.5

    p = make_smoother("passthrough")
    assert isinstance(p, PassthroughSmoother)


def test_make_smoother_unknown_raises() -> None:
    with pytest.raises(KeyError):
        make_smoother("does_not_exist")
