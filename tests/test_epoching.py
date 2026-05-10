from __future__ import annotations

import numpy as np

from bci.epoching import extract_trials, sliding_windows


def _build_continuous(
    fs: float = 128.0,
    duration_s: float = 30.0,
) -> tuple[np.ndarray, np.ndarray]:
    n = int(duration_s * fs)
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((2, n)).astype(np.float32)
    timestamps = np.arange(n) / fs + 1000.0  # arbitrary LSL clock offset
    return raw, timestamps


def test_extract_trials_basic_shape_and_labels() -> None:
    raw, ts = _build_continuous()
    fs = 128.0
    markers = [
        (ts[100], 0),
        (ts[1000], 1),
        (ts[2000], 0),
        (ts[3000], 1),
    ]
    X, y = extract_trials(raw, ts, markers, trial_len_s=4.0, fs=fs)
    assert X.shape == (4, 2, 512)
    np.testing.assert_array_equal(y, [0, 1, 0, 1])


def test_extract_trials_ignores_rest_marker_99() -> None:
    raw, ts = _build_continuous()
    markers_no_rest = [(ts[100], 0), (ts[1000], 1)]
    markers_with_rest = [
        (ts[100], 0),
        (ts[600], 99),
        (ts[1000], 1),
        (ts[1500], 99),
    ]
    Xa, ya = extract_trials(raw, ts, markers_no_rest, 4.0, 128.0)
    Xb, yb = extract_trials(raw, ts, markers_with_rest, 4.0, 128.0)
    np.testing.assert_array_equal(Xa, Xb)
    np.testing.assert_array_equal(ya, yb)


def test_extract_trials_skips_markers_past_end() -> None:
    raw, ts = _build_continuous(duration_s=10.0)
    fs = 128.0
    # Last marker placed too close to the end: trial would overflow.
    markers = [(ts[0], 0), (ts[-50], 1)]
    X, y = extract_trials(raw, ts, markers, trial_len_s=4.0, fs=fs)
    assert X.shape == (1, 2, 512)
    assert y.tolist() == [0]


def test_extract_trials_preserves_signal() -> None:
    raw, ts = _build_continuous()
    fs = 128.0
    markers = [(ts[256], 0)]
    X, _ = extract_trials(raw, ts, markers, 4.0, fs)
    np.testing.assert_array_equal(X[0], raw[:, 256 : 256 + 512])


def test_extract_trials_empty_returns_correct_shape() -> None:
    raw, ts = _build_continuous()
    X, y = extract_trials(raw, ts, [(ts[10], 99)], 4.0, 128.0)
    assert X.shape == (0, 2, 512)
    assert y.shape == (0,)


def test_sliding_windows_count_and_groups() -> None:
    rng = np.random.default_rng(0)
    trials = rng.standard_normal((40, 2, 512)).astype(np.float32)
    labels = np.array([0] * 20 + [1] * 20, dtype=np.int64)
    X, y, group = sliding_windows(
        trials, labels, window_samples=256, stride_samples=64
    )
    # (512 - 256) // 64 + 1 == 5 windows per trial -> 200 total
    assert X.shape == (200, 2, 256)
    assert y.shape == (200,)
    assert group.shape == (200,)
    # Each trial id appears exactly 5 times.
    counts = np.bincount(group)
    assert counts.shape == (40,)
    assert np.all(counts == 5)
    # Labels track their trial.
    for t in range(40):
        mask = group == t
        assert np.all(y[mask] == labels[t])


def test_sliding_windows_first_window_matches_raw() -> None:
    trials = np.arange(2 * 2 * 8).reshape(2, 2, 8).astype(np.float32)
    labels = np.array([0, 1])
    X, _, _ = sliding_windows(
        trials, labels, window_samples=4, stride_samples=2
    )
    np.testing.assert_array_equal(X[0], trials[0, :, :4])
    np.testing.assert_array_equal(X[1], trials[0, :, 2:6])
    np.testing.assert_array_equal(X[3], trials[1, :, :4])


def test_sliding_windows_rejects_window_longer_than_trial() -> None:
    trials = np.zeros((1, 2, 10))
    labels = np.array([0])
    try:
        sliding_windows(trials, labels, window_samples=20, stride_samples=2)
    except ValueError:
        return
    raise AssertionError("Expected ValueError for too-long window")
