"""Mock Emotiv-EPOC-X-style EEG LSL outlet for development.

Pushes a continuous (n_samples, 19) stream at ~fs Hz mimicking the
EPOC X layout:

    19 = 3 prefix (counter / interpolated / signal_quality)
       + 14 EEG (AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4, F8, AF4)
       + 2 extras (aux channels)

Channel offset 3 is what bci.lsl_io.EEGReceiver will skip on connect.
The EEG channels embed alternating left/right motor-imagery patterns
on the two motor channels (default FC5 / FC6) so dev_realtime_log.py
can be sanity-checked against a known schedule.

Run from the repo root:
    python scripts/dev_fake_lsl_stream.py
    python scripts/dev_fake_lsl_stream.py --mode noise
    python scripts/dev_fake_lsl_stream.py --motor-channels FC5 FC6
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bci.logging_setup import setup_logging  # noqa: E402
from tests._synth import make_mi_trial  # noqa: E402

logger = logging.getLogger("bci.dev_fake_lsl_stream")

CHANNEL_OFFSET = 3
EXTRA_CHANNELS = 2
N_EEG = 14  # EPOC X only
EPOCX_LABELS: tuple[str, ...] = (
    "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
)


def _build_stream_info(fs: float, name: str) -> tuple[StreamInfo, int]:
    total = CHANNEL_OFFSET + N_EEG + EXTRA_CHANNELS
    info = StreamInfo(
        name=name,
        type="EEG",
        channel_count=total,
        nominal_srate=fs,
        channel_format="float32",
        source_id="mock_emotiv_epocx",
    )
    desc = info.desc()
    desc.append_child_value("manufacturer", "Emotiv")

    chans = desc.append_child("channels")
    for i in range(total):
        ch = chans.append_child("channel")
        if i < CHANNEL_OFFSET:
            label = ("counter", "interpolated", "signal_quality")[i]
        elif i < CHANNEL_OFFSET + N_EEG:
            label = EPOCX_LABELS[i - CHANNEL_OFFSET]
        else:
            label = f"aux{i - CHANNEL_OFFSET - N_EEG}"
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    return info, total


def _generate_mi_block(
    label: int,
    n_samples: int,
    fs: float,
    motor_indices: tuple[int, int],
    rng: np.random.Generator,
) -> np.ndarray:
    """Return (n_samples, N_EEG) with the requested class pattern.

    Discriminative MI signal sits on the two ``motor_indices`` channels;
    the remaining 12 are baseline noise so CAR-on (14ch) decoders still
    see a non-trivial signal.
    """
    out = rng.standard_normal((n_samples, N_EEG)).astype(np.float32) * 1.5
    if label not in (0, 1):
        return out
    pair = make_mi_trial(
        label=label,
        n_samples=n_samples,
        fs=fs,
        n_channels=2,
        rng=rng,
    )  # (2, n_samples)
    out[:, motor_indices[0]] = pair[0]
    out[:, motor_indices[1]] = pair[1]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fs", type=float, default=128.0)
    parser.add_argument(
        "--mode",
        choices=["alternating", "noise", "fixed-left", "fixed-right"],
        default="alternating",
    )
    parser.add_argument("--switch-s", type=float, default=5.0)
    parser.add_argument("--name", default="MockEmotiv")
    parser.add_argument(
        "--motor-channels",
        nargs=2,
        metavar=("LEFT", "RIGHT"),
        default=["FC5", "FC6"],
        help="Channel labels carrying the discriminative MI pattern.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--duration", type=float, default=0.0, help="0 = run until Ctrl-C"
    )
    args = parser.parse_args()

    motor_indices = []
    for name in args.motor_channels:
        if name not in EPOCX_LABELS:
            parser.error(
                f"--motor-channels {name!r} not in EPOC X montage {EPOCX_LABELS}"
            )
        motor_indices.append(EPOCX_LABELS.index(name))
    motor_indices_t = (motor_indices[0], motor_indices[1])

    setup_logging(REPO_ROOT / "logs", level="INFO")
    info, total_channels = _build_stream_info(fs=args.fs, name=args.name)
    outlet = StreamOutlet(info, chunk_size=16, max_buffered=360)
    logger.info(
        "Streaming %s (type=EEG, total_ch=%d, eeg_ch=%d, fs=%g, mode=%s, "
        "motor=%s @ idx %s)",
        args.name,
        total_channels,
        N_EEG,
        args.fs,
        args.mode,
        args.motor_channels,
        motor_indices_t,
    )

    stop = False

    def _on_signal(signum, frame):  # noqa: ANN001 -- signal API
        nonlocal stop
        stop = True
        logger.info("Caught signal %d, stopping", signum)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    rng = np.random.default_rng(args.seed)
    chunk_n = 16
    period = chunk_n / args.fs
    t_next = time.time()
    t0 = time.time()

    sample_idx = 0
    while not stop:
        if args.duration > 0 and (time.time() - t0) >= args.duration:
            break

        # Decide current label for this chunk window.
        elapsed = time.time() - t0
        if args.mode == "noise":
            label: int | None = None
        elif args.mode == "fixed-left":
            label = 0
        elif args.mode == "fixed-right":
            label = 1
        else:  # alternating
            label = int(elapsed // args.switch_s) % 2

        eeg_block = _generate_mi_block(
            label if label is not None else -1,
            n_samples=chunk_n,
            fs=args.fs,
            motor_indices=motor_indices_t,
            rng=rng,
        )
        full = np.zeros((chunk_n, total_channels), dtype=np.float32)
        full[:, 0] = (np.arange(sample_idx, sample_idx + chunk_n) % 256).astype(
            np.float32
        )
        full[:, 1] = 0.0
        full[:, 2] = 1.0  # nominal signal quality
        full[:, CHANNEL_OFFSET : CHANNEL_OFFSET + N_EEG] = eeg_block
        full[:, CHANNEL_OFFSET + N_EEG :] = (
            rng.standard_normal((chunk_n, EXTRA_CHANNELS)).astype(np.float32) * 0.5
        )

        outlet.push_chunk(full.tolist(), local_clock())
        sample_idx += chunk_n
        t_next += period
        sleep_for = t_next - time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)
        else:
            # Falling behind: skip catching up so we don't burst.
            t_next = time.time()

    logger.info("Stopped after pushing %d samples", sample_idx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
