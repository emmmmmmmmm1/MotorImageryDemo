from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from bci.lsl_io import RingBuffer


def test_push_get_last_basic() -> None:
    rb = RingBuffer(n_channels=2, capacity_samples=10)
    chunk = np.array(
        [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]], dtype=np.float64
    )
    rb.push(chunk)
    assert rb.n_filled() == 3
    out = rb.get_last(3)
    np.testing.assert_array_equal(out, chunk.T)


def test_push_wraps_around() -> None:
    rb = RingBuffer(n_channels=1, capacity_samples=5)
    rb.push(np.arange(3).reshape(3, 1).astype(float))  # [0,1,2]
    rb.push(np.arange(3, 7).reshape(4, 1).astype(float))  # [3,4,5,6]
    # Capacity 5, total pushed 7, last 5 are [2,3,4,5,6]
    assert rb.n_filled() == 5
    np.testing.assert_array_equal(
        rb.get_last(5), np.array([[2.0, 3.0, 4.0, 5.0, 6.0]])
    )
    np.testing.assert_array_equal(
        rb.get_last(3), np.array([[4.0, 5.0, 6.0]])
    )


def test_push_larger_than_capacity_keeps_tail() -> None:
    rb = RingBuffer(n_channels=1, capacity_samples=4)
    big = np.arange(10).reshape(10, 1).astype(float)
    rb.push(big)
    assert rb.n_filled() == 4
    np.testing.assert_array_equal(
        rb.get_last(4), np.array([[6.0, 7.0, 8.0, 9.0]])
    )


def test_get_last_zero_returns_empty() -> None:
    rb = RingBuffer(n_channels=2, capacity_samples=5)
    rb.push(np.ones((3, 2)))
    out = rb.get_last(0)
    assert out.shape == (2, 0)


def test_get_last_more_than_filled_raises() -> None:
    rb = RingBuffer(n_channels=1, capacity_samples=10)
    rb.push(np.zeros((4, 1)))
    with pytest.raises(ValueError):
        rb.get_last(5)


def test_clear_resets_state() -> None:
    rb = RingBuffer(n_channels=2, capacity_samples=10)
    rb.push(np.ones((5, 2)))
    rb.clear()
    assert rb.n_filled() == 0
    with pytest.raises(ValueError):
        rb.get_last(1)


def test_concurrent_push_and_get_does_not_raise() -> None:
    """Two writer threads + one reader thread for 1 second.

    Goal: verify no AssertionError or shape mismatch ever surfaces; we
    do not assert on ordering since two writers race for write slots.
    """
    rb = RingBuffer(n_channels=2, capacity_samples=512)
    stop = threading.Event()
    errors: list[BaseException] = []

    def writer(rng_seed: int, chunk_n: int) -> None:
        rng = np.random.default_rng(rng_seed)
        try:
            while not stop.is_set():
                rb.push(rng.standard_normal((chunk_n, 2)))
                time.sleep(0.001)
        except BaseException as exc:  # pragma: no cover -- must not happen
            errors.append(exc)

    def reader() -> None:
        try:
            while not stop.is_set():
                filled = rb.n_filled()
                if filled >= 64:
                    out = rb.get_last(64)
                    assert out.shape == (2, 64)
                time.sleep(0.0005)
        except BaseException as exc:  # pragma: no cover -- must not happen
            errors.append(exc)

    threads = [
        threading.Thread(target=writer, args=(1, 8), daemon=True),
        threading.Thread(target=writer, args=(2, 13), daemon=True),
        threading.Thread(target=reader, daemon=True),
    ]
    for t in threads:
        t.start()
    time.sleep(1.0)
    stop.set()
    for t in threads:
        t.join(timeout=2.0)
    assert not errors, f"thread errors: {errors}"
    # Final sanity: buffer is fully primed.
    assert rb.n_filled() == rb.capacity


def test_get_last_full_capacity() -> None:
    rb = RingBuffer(n_channels=1, capacity_samples=4)
    rb.push(np.array([[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]]))
    # capacity 4, last 4 should be [3,4,5,6]
    np.testing.assert_array_equal(
        rb.get_last(4), np.array([[3.0, 4.0, 5.0, 6.0]])
    )
