"""Synthetic motor-imagery EEG generator for unit tests.

Channel 0 emulates C3, channel 1 emulates C4. Class 0 (left MI) raises
mu-band power on channel 0 and lowers it on channel 1; class 1 (right
MI) reverses the pattern. Any extra channels carry neutral mu power so
the helper works for both 2ch and 14ch test scenarios.
"""

from __future__ import annotations

import numpy as np


def _trial(
    n_samples: int,
    fs: float,
    mu_amp: float,
    beta_amp: float,
    noise_amp: float,
    rng: np.random.Generator,
) -> np.ndarray:
    t = np.arange(n_samples) / fs
    mu_freq = 10.0 + rng.uniform(-1.0, 1.0)
    beta_freq = 20.0 + rng.uniform(-2.0, 2.0)
    phase_mu = rng.uniform(0.0, 2.0 * np.pi)
    phase_beta = rng.uniform(0.0, 2.0 * np.pi)
    mu = mu_amp * np.sin(2 * np.pi * mu_freq * t + phase_mu)
    beta = beta_amp * np.sin(2 * np.pi * beta_freq * t + phase_beta)
    noise = rng.standard_normal(n_samples) * noise_amp
    return mu + beta + noise


def generate_synthetic_mi(
    n_trials_per_class: int = 20,
    fs: float = 128.0,
    trial_len_s: float = 4.0,
    n_channels: int = 2,
    high_mu: float = 6.0,
    low_mu: float = 1.0,
    beta_amp: float = 1.0,
    noise_amp: float = 1.5,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, y) with X shape (n_total, n_channels, n_samples)."""
    if n_channels < 2:
        raise ValueError("n_channels must be >= 2 (C3, C4 are required).")

    rng = np.random.default_rng(seed)
    n_samples = int(round(trial_len_s * fs))
    n_total = 2 * n_trials_per_class
    X = np.zeros((n_total, n_channels, n_samples), dtype=np.float32)
    y = np.zeros(n_total, dtype=np.int64)
    neutral_mu = 0.5 * (high_mu + low_mu)

    idx = 0
    for cls in (0, 1):
        for _ in range(n_trials_per_class):
            for ch in range(n_channels):
                if ch == 0:
                    mu_amp = high_mu if cls == 0 else low_mu
                elif ch == 1:
                    mu_amp = low_mu if cls == 0 else high_mu
                else:
                    mu_amp = neutral_mu
                X[idx, ch] = _trial(
                    n_samples, fs, mu_amp, beta_amp, noise_amp, rng
                )
            y[idx] = cls
            idx += 1

    perm = rng.permutation(n_total)
    return X[perm], y[perm]


def generate_continuous_mi(
    markers: list[tuple[float, int]],
    fs: float = 128.0,
    trial_len_s: float = 4.0,
    pre_s: float = 1.0,
    post_s: float = 2.0,
    n_channels: int = 2,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (raw, timestamps) where raw is (n_channels, T).

    markers: list of (t_lsl_seconds, label) with label in {0, 1}. Each
    marker triggers a trial-shaped chunk in the continuous stream.
    """
    rng = np.random.default_rng(seed)
    if not markers:
        raise ValueError("markers must be non-empty")
    t_start = markers[0][0] - pre_s
    t_end = markers[-1][0] + trial_len_s + post_s
    n_total = int(round((t_end - t_start) * fs))
    timestamps = t_start + np.arange(n_total) / fs

    raw = rng.standard_normal((n_channels, n_total)).astype(np.float32) * 1.5

    n_trial = int(round(trial_len_s * fs))
    for t_marker, label in markers:
        i0 = int(round((t_marker - t_start) * fs))
        if i0 < 0 or i0 + n_trial > n_total:
            continue
        seg, _ = generate_synthetic_mi(
            n_trials_per_class=1,
            fs=fs,
            trial_len_s=trial_len_s,
            n_channels=n_channels,
            seed=int(rng.integers(0, 2**31 - 1)),
        )
        # Pick the trial whose label matches the marker's
        chosen = seg[0] if (seg.shape[0] >= 1 and label == 0) else seg[-1]
        raw[:, i0 : i0 + n_trial] += chosen

    return raw, timestamps
