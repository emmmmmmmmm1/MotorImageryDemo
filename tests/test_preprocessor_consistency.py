"""Phase 3.2: offline transform == online transform_chunk after warm-up.

This is the core invariant that lets calibration (one-shot) and
realtime (chunked) match: same sos coefficients are applied, with the
chunked variant carrying zi state across chunks.
"""

from __future__ import annotations

import numpy as np
import pytest

from bci.config import PreprocessingConfig
from bci.preprocessing import Preprocessor


def _signal(fs: float, dur_s: float, n_channels: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(dur_s * fs)
    t = np.arange(n) / fs
    base = np.sin(2 * np.pi * 10 * t) + 0.5 * np.sin(2 * np.pi * 20 * t)
    sig = np.tile(base, (n_channels, 1))
    sig += rng.standard_normal(sig.shape) * 0.5
    # Make channels slightly different so CAR is nontrivial.
    for ch in range(n_channels):
        sig[ch] += 0.1 * (ch + 1)
    return sig.astype(np.float64)


def _chunked_transform(
    pre: Preprocessor, sig: np.ndarray, chunk_samples: int
) -> np.ndarray:
    n_channels, n_samples = sig.shape
    pre.reset_filter_state(n_channels=n_channels)
    out = np.empty_like(sig)
    cursor = 0
    while cursor < n_samples:
        end = min(cursor + chunk_samples, n_samples)
        chunk = sig[:, cursor:end].T  # (n_samples_chunk, n_channels)
        out[:, cursor:end] = pre.transform_chunk(chunk).T
        cursor = end
    return out


@pytest.mark.parametrize(
    "n_channels, expect_car",
    [(2, False), (4, True)],
)
@pytest.mark.parametrize("chunk_samples", [16, 32, 64, 128])
def test_offline_online_match_after_warmup(
    n_channels: int, expect_car: bool, chunk_samples: int
) -> None:
    fs = 128.0
    dur_s = 8.0
    sig = _signal(fs=fs, dur_s=dur_s, n_channels=n_channels, seed=0)

    cfg = PreprocessingConfig(
        fs=fs,
        channel_order=[f"ch{i}" for i in range(n_channels)],
    )
    assert cfg.apply_car is expect_car  # sanity: 2ch=off, 4ch=on

    pre_off = Preprocessor(cfg)
    out_offline = pre_off.transform(sig)

    pre_on = Preprocessor(cfg)
    out_online = _chunked_transform(pre_on, sig, chunk_samples=chunk_samples)

    assert out_offline.shape == out_online.shape

    # Drop the first 1s of transient before comparing. atol=1e-5
    # absorbs IEEE-754 noise from sosfilt; the offline pass uses zero
    # initial state while the online pass uses sosfilt_zi steady-state.
    skip = int(fs)
    np.testing.assert_allclose(
        out_offline[:, skip:],
        out_online[:, skip:],
        atol=1e-5,
    )


def test_transform_chunk_requires_reset() -> None:
    cfg = PreprocessingConfig(fs=128.0, channel_order=["C3", "C4"])
    pre = Preprocessor(cfg)
    chunk = np.zeros((16, 2))
    with pytest.raises(RuntimeError):
        pre.transform_chunk(chunk)


def test_transform_chunk_handles_two_channels_independently() -> None:
    """Channel zi states must not leak across channels."""
    cfg = PreprocessingConfig(fs=128.0, channel_order=["C3", "C4"])
    pre = Preprocessor(cfg)
    pre.reset_filter_state(n_channels=2)

    rng = np.random.default_rng(0)
    chunk_a = rng.standard_normal((64, 2))
    chunk_b = rng.standard_normal((64, 2))

    pre.reset_filter_state(n_channels=2)
    full = pre.transform_chunk(np.concatenate([chunk_a, chunk_b], axis=0))

    pre.reset_filter_state(n_channels=2)
    a_out = pre.transform_chunk(chunk_a)
    b_out = pre.transform_chunk(chunk_b)
    chunked = np.concatenate([a_out, b_out], axis=0)

    np.testing.assert_allclose(full, chunked, atol=1e-9)
