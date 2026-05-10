"""In-process EEGReceiver tests against an EPOC X-shaped fake stream.

The outlet and the receiver share a process; pylsl handles loopback
discovery. Each test uses a unique source_id so streams don't alias.
"""

from __future__ import annotations

import time

import numpy as np
import pytest
from pylsl import StreamInfo, StreamOutlet, local_clock

from bci.config import PreprocessingConfig
from bci.lsl_io import EEGReceiver
from bci.preprocessing import Preprocessor

FS = 128.0
CHUNK_SAMPLES = 16
N_EEG = 14
TOTAL_CHANNELS = 3 + N_EEG + 2  # offset + EEG + extras = 19
EPOCX_LABELS: tuple[str, ...] = (
    "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
)


def _make_epocx_outlet(source_id: str) -> StreamOutlet:
    info = StreamInfo(
        name=f"TestEpocX_{source_id}",
        type="EEG",
        channel_count=TOTAL_CHANNELS,
        nominal_srate=FS,
        channel_format="float32",
        source_id=source_id,
    )
    desc = info.desc()
    desc.append_child_value("manufacturer", "Emotiv")
    chans = desc.append_child("channels")
    for i in range(TOTAL_CHANNELS):
        ch = chans.append_child("channel")
        if i < 3:
            ch.append_child_value(
                "label", ("counter", "interpolated", "signal_quality")[i]
            )
        elif i < 3 + N_EEG:
            ch.append_child_value("label", EPOCX_LABELS[i - 3])
        else:
            ch.append_child_value("label", f"aux{i - 3 - N_EEG}")
    return StreamOutlet(info, chunk_size=CHUNK_SAMPLES, max_buffered=360)


def _push_block(outlet: StreamOutlet, n_samples: int) -> None:
    """Push a chunk where each EEG channel carries a unique ramp.

    Channel-distinct content lets us verify the offset and the channel
    selection logic by reading ringbuffer values back.
    """
    block = np.zeros((n_samples, TOTAL_CHANNELS), dtype=np.float32)
    for ci in range(N_EEG):
        # ch index ci -> ramp from ci to ci+1 across the chunk
        block[:, 3 + ci] = np.linspace(ci, ci + 1, n_samples)
    outlet.push_chunk(block.tolist(), local_clock())


def _drain_outlet(outlet: StreamOutlet) -> None:
    del outlet


def test_connect_parses_epocx_layout() -> None:
    outlet = _make_epocx_outlet(source_id="conn_full")
    try:
        rx = EEGReceiver(stream_type="EEG", capacity_seconds=2.0)
        info = rx.connect()
        assert info["n_channels"] == 14
        assert info["total_channels"] == TOTAL_CHANNELS
        assert info["channel_offset"] == 3
        assert info["channel_names"] == list(EPOCX_LABELS)
        assert info["all_eeg_channel_names"] == list(EPOCX_LABELS)
        assert info["manufacturer"] == "Emotiv"
        assert info["fs"] == pytest.approx(FS)
    finally:
        _drain_outlet(outlet)


def test_streaming_fills_raw_buffer_full_14ch() -> None:
    outlet = _make_epocx_outlet(source_id="raw_full")
    try:
        rx = EEGReceiver(stream_type="EEG", capacity_seconds=2.0)
        rx.connect()
        rx.start_streaming()
        try:
            for _ in range(20):
                _push_block(outlet, CHUNK_SAMPLES)
                time.sleep(CHUNK_SAMPLES / FS)
            time.sleep(0.2)
            assert rx.n_filled_raw() >= 64
            raw = rx.get_last_raw(64)
            assert raw.shape == (14, 64)
            for ci in range(N_EEG):
                # Each row's std reflects its ramp's gradient, all >0.
                assert np.std(raw[ci]) > 0
        finally:
            rx.stop_streaming()
    finally:
        _drain_outlet(outlet)


def test_channel_selection_subset_two_channels() -> None:
    outlet = _make_epocx_outlet(source_id="raw_sel")
    try:
        rx = EEGReceiver(
            stream_type="EEG",
            capacity_seconds=2.0,
            channel_selection=["FC5", "FC6"],
        )
        info = rx.connect()
        assert info["n_channels"] == 2
        assert info["channel_names"] == ["FC5", "FC6"]
        assert info["all_eeg_channel_names"] == list(EPOCX_LABELS)
        rx.start_streaming()
        try:
            for _ in range(20):
                _push_block(outlet, CHUNK_SAMPLES)
                time.sleep(CHUNK_SAMPLES / FS)
            time.sleep(0.2)
            assert rx.n_filled_raw() >= 64
            raw = rx.get_last_raw(64)
            assert raw.shape == (2, 64)
            # Means of the FC5 (idx 3) and FC6 (idx 10) ramps differ.
            fc5_mean = float(raw[0].mean())
            fc6_mean = float(raw[1].mean())
            # FC5 ramp goes ~3 -> ~4, FC6 ramp goes ~10 -> ~11.
            assert 2.5 < fc5_mean < 5.0
            assert 9.5 < fc6_mean < 12.0
        finally:
            rx.stop_streaming()
    finally:
        _drain_outlet(outlet)


def test_channel_selection_unknown_channel_raises() -> None:
    outlet = _make_epocx_outlet(source_id="bad_sel")
    try:
        rx = EEGReceiver(
            stream_type="EEG",
            channel_selection=["AF3", "DOES_NOT_EXIST"],
        )
        with pytest.raises(RuntimeError, match="not in stream EEG labels"):
            rx.connect()
    finally:
        _drain_outlet(outlet)


def test_attached_preprocessor_filters_into_filtered_buffer() -> None:
    outlet = _make_epocx_outlet(source_id="filt_full")
    try:
        rx = EEGReceiver(stream_type="EEG", capacity_seconds=3.0)
        rx.connect()
        cfg = PreprocessingConfig(
            fs=FS, channel_order=list(EPOCX_LABELS)
        )
        pre = Preprocessor(cfg)
        rx.attach_preprocessor(pre)
        rx.start_streaming()
        try:
            for _ in range(40):
                _push_block(outlet, CHUNK_SAMPLES)
                time.sleep(CHUNK_SAMPLES / FS)
            time.sleep(0.3)
            assert rx.n_filled_filtered() >= 128
            filt = rx.get_last_filtered(128)
            raw = rx.get_last_raw(128)
            assert filt.shape == raw.shape == (14, 128)
            assert not np.allclose(filt, raw)
        finally:
            rx.stop_streaming()
    finally:
        _drain_outlet(outlet)


def test_recording_returns_concatenated_raw_and_timestamps() -> None:
    outlet = _make_epocx_outlet(source_id="rec_full")
    try:
        rx = EEGReceiver(stream_type="EEG", capacity_seconds=4.0)
        rx.connect()
        rx.start_streaming()
        try:
            time.sleep(0.2)
            rx.start_recording()
            t0 = time.time()
            while time.time() - t0 < 0.6:
                _push_block(outlet, CHUNK_SAMPLES)
                time.sleep(CHUNK_SAMPLES / FS)
            time.sleep(0.2)
            raw, ts = rx.stop_recording()
            assert raw.shape[0] == 14
            assert raw.shape[1] == ts.shape[0]
            assert raw.shape[1] >= int(FS * 0.3)
            assert np.all(np.diff(ts) >= 0)
        finally:
            rx.stop_streaming()
    finally:
        _drain_outlet(outlet)


def test_is_stalled_flips_when_outlet_stops() -> None:
    outlet = _make_epocx_outlet(source_id="stall_full")
    try:
        rx = EEGReceiver(
            stream_type="EEG", capacity_seconds=2.0, stall_timeout_s=0.5
        )
        rx.connect()
        rx.start_streaming()
        try:
            for _ in range(10):
                _push_block(outlet, CHUNK_SAMPLES)
                time.sleep(CHUNK_SAMPLES / FS)
            time.sleep(0.1)
            assert rx.is_stalled() is False
        finally:
            pass
        time.sleep(1.0)
        assert rx.is_stalled() is True
        rx.stop_streaming()
    finally:
        _drain_outlet(outlet)


def test_unexpected_emotiv_layout_raises() -> None:
    info = StreamInfo(
        name="WeirdEmotiv",
        type="EEG",
        channel_count=11,  # only 19 (EPOC X) is supported
        nominal_srate=FS,
        channel_format="float32",
        source_id="weird_emotiv",
    )
    info.desc().append_child_value("manufacturer", "Emotiv")
    chans = info.desc().append_child("channels")
    for i in range(11):
        ch = chans.append_child("channel")
        ch.append_child_value("label", f"ch{i}")
    outlet = StreamOutlet(info)
    try:
        rx = EEGReceiver(stream_type="EEG")
        with pytest.raises(RuntimeError, match="unexpected channel_count"):
            rx.connect()
    finally:
        _drain_outlet(outlet)
