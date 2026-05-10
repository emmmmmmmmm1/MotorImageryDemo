"""Bring up all five LSL streams in one process and verify round trips.

Streams (matching design v7 §3):
    EEG       -- mock EPOC X publisher
    Markers   -- this script publishes (label) ints
    Commands  -- this script publishes command strings
    Status    -- StatusPublisher
    BCI_Proba -- ProbaPublisher

The script then resolves each stream type, pulls samples for a few
seconds, and prints a summary. Useful as a smoke test before wiring up
service.py / Unity.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
from pylsl import (
    StreamInfo,
    StreamInlet,
    StreamOutlet,
    local_clock,
    resolve_byprop,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bci.logging_setup import setup_logging  # noqa: E402
from bci.lsl_io import (  # noqa: E402
    MarkerReceiver,
    ProbaPublisher,
    StatusPublisher,
)
from tests._synth import make_mi_trial  # noqa: E402

logger = logging.getLogger("bci.dev_lsl_loopback")

FS = 128.0
N_EEG = 14
TOTAL_CHANNELS = 3 + N_EEG + 2


def _make_eeg_outlet() -> StreamOutlet:
    info = StreamInfo(
        name="LoopbackEEG",
        type="EEG",
        channel_count=TOTAL_CHANNELS,
        nominal_srate=FS,
        channel_format="float32",
        source_id="loopback_eeg",
    )
    desc = info.desc()
    desc.append_child_value("manufacturer", "Emotiv")
    chans = desc.append_child("channels")
    labels = (
        ("counter", "interpolated", "signal_quality")
        + ("AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
           "O2", "P8", "T8", "FC6", "F4", "F8", "AF4")
        + ("aux0", "aux1")
    )
    for name in labels:
        ch = chans.append_child("channel")
        ch.append_child_value("label", name)
    return StreamOutlet(info, chunk_size=16, max_buffered=360)


def _make_marker_outlet() -> StreamOutlet:
    info = StreamInfo(
        name="LoopbackMarkers",
        type="Markers",
        channel_count=1,
        nominal_srate=0.0,
        channel_format="int32",
        source_id="loopback_markers",
    )
    return StreamOutlet(info)


def _make_command_outlet() -> StreamOutlet:
    info = StreamInfo(
        name="LoopbackCommands",
        type="Commands",
        channel_count=1,
        nominal_srate=0.0,
        channel_format="string",
        source_id="loopback_commands",
    )
    return StreamOutlet(info)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration-s",
        type=float,
        default=15.0,
        help="How long to publish loopback samples before summarizing.",
    )
    args = parser.parse_args()

    setup_logging(REPO_ROOT / "logs", level="INFO")
    logger.info("Bringing up 5 LSL streams (EEG, Markers, Commands, Status, BCI_Proba)")

    eeg_out = _make_eeg_outlet()
    marker_out = _make_marker_outlet()
    cmd_out = _make_command_outlet()
    status_pub = StatusPublisher(name="LoopbackStatus", source_id="loopback_status")
    proba_pub = ProbaPublisher(
        n_classes=2, name="LoopbackProba", source_id="loopback_proba"
    )

    rx_marker = MarkerReceiver()
    rx_marker.connect()
    cmd_streams = resolve_byprop("source_id", "loopback_commands", timeout=5.0)
    if not cmd_streams:
        raise RuntimeError("No LoopbackCommands stream found")
    cmd_inlet = StreamInlet(cmd_streams[0])
    cmd_inlet.open_stream(timeout=2.0)

    eeg_streams = resolve_byprop("type", "EEG", timeout=5.0)
    eeg_inlet = StreamInlet(
        next(s for s in eeg_streams if s.source_id() == "loopback_eeg")
    )
    eeg_inlet.open_stream(timeout=2.0)

    status_streams = resolve_byprop("type", "Status", timeout=5.0)
    status_inlet = StreamInlet(
        next(s for s in status_streams if s.source_id() == "loopback_status")
    )
    status_inlet.open_stream(timeout=2.0)

    proba_streams = resolve_byprop("type", "BCI_Proba", timeout=5.0)
    proba_inlet = StreamInlet(
        next(s for s in proba_streams if s.source_id() == "loopback_proba")
    )
    proba_inlet.open_stream(timeout=2.0)

    time.sleep(0.5)

    rng = np.random.default_rng(0)
    chunk_n = 16
    period = chunk_n / FS
    n_eeg_chunks_pushed = 0
    n_markers_pushed = 0
    n_commands_pushed = 0
    n_proba_pushed = 0
    n_status_pushed = 0

    t_start = time.time()
    next_eeg_t = t_start
    sample_idx = 0
    while time.time() - t_start < args.duration_s:
        if time.time() >= next_eeg_t:
            block = np.zeros((chunk_n, TOTAL_CHANNELS), dtype=np.float32)
            block[:, 0] = (np.arange(sample_idx, sample_idx + chunk_n) % 256).astype(
                np.float32
            )
            block[:, 2] = 1.0
            block[:, 3 : 3 + 2] = make_mi_trial(
                label=int((time.time() - t_start) // 1.0) % 2,
                n_samples=chunk_n,
                fs=FS,
                n_channels=2,
                rng=rng,
            ).T
            eeg_out.push_chunk(block.tolist(), local_clock())
            sample_idx += chunk_n
            n_eeg_chunks_pushed += 1
            next_eeg_t += period

        if int((time.time() - t_start) * 4) > n_markers_pushed:
            marker_out.push_sample([n_markers_pushed % 2], local_clock())
            n_markers_pushed += 1

        if int((time.time() - t_start) * 2) > n_commands_pushed:
            cmd_out.push_sample([f"cmd_{n_commands_pushed}"])
            n_commands_pushed += 1

        if int((time.time() - t_start) * 4) > n_proba_pushed:
            p = np.array([0.5 + 0.4 * np.sin(time.time()), 0.0])
            p[1] = 1.0 - p[0]
            proba_pub.push(p)
            n_proba_pushed += 1

        if int((time.time() - t_start) * 2) > n_status_pushed:
            status_pub.push(f"tick:{n_status_pushed}")
            n_status_pushed += 1

        time.sleep(0.005)

    time.sleep(0.5)
    eeg_samples, eeg_ts = eeg_inlet.pull_chunk(timeout=0.5, max_samples=2048)
    markers = rx_marker.pull()
    cmd_samples, _ = cmd_inlet.pull_chunk(timeout=0.5, max_samples=128)
    cmds = [str(sample[0]) for sample in cmd_samples]
    status_samples, _ = status_inlet.pull_chunk(timeout=0.5, max_samples=128)
    proba_samples, _ = proba_inlet.pull_chunk(timeout=0.5, max_samples=128)

    logger.info(
        "summary: eeg pushed=%d, eeg received samples=%d",
        n_eeg_chunks_pushed,
        len(eeg_samples),
    )
    logger.info("summary: markers pushed=%d, received=%d", n_markers_pushed, len(markers))
    logger.info("summary: commands pushed=%d, received=%d", n_commands_pushed, len(cmds))
    logger.info(
        "summary: status pushed=%d, received=%d",
        n_status_pushed,
        len(status_samples),
    )
    logger.info(
        "summary: proba pushed=%d, received=%d",
        n_proba_pushed,
        len(proba_samples),
    )

    failures: list[str] = []
    if len(eeg_samples) == 0:
        failures.append("EEG")
    if len(markers) != n_markers_pushed:
        failures.append(f"Markers ({len(markers)}/{n_markers_pushed})")
    if len(cmds) != n_commands_pushed:
        failures.append(f"Commands ({len(cmds)}/{n_commands_pushed})")
    if len(status_samples) != n_status_pushed:
        failures.append(f"Status ({len(status_samples)}/{n_status_pushed})")
    if len(proba_samples) != n_proba_pushed:
        failures.append(f"Proba ({len(proba_samples)}/{n_proba_pushed})")
    if failures:
        logger.error("loopback failures: %s", failures)
        return 1
    logger.info("OK: 5 LSL streams round-tripped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
