"""Realtime decoder loop with optional warm-up impulse measurement.

Two modes:

  1. ``--measure-warmup`` (no LSL, no bundle needed)

     Pushes an impulse through a fresh Preprocessor and reports the
     time until the chunked output decays below 1% of peak. Use the
     value (plus a small safety margin) to set ``realtime.warmup_s``
     in configs/default.yaml.

  2. Default: bundle-driven loop

     Loads a saved bundle, attaches its Preprocessor to an EEGReceiver
     resolved on type=EEG, waits ``--warmup-s`` for filter transients,
     then logs smoothed probabilities at ``--stride-ms`` intervals.

Examples:
    python scripts/dev_realtime_log.py --measure-warmup
    python scripts/dev_realtime_log.py --bundle bundles/synth_*.joblib \
        --channels FC5 FC6 --duration 10
"""

from __future__ import annotations

import argparse
import glob
import logging
import signal
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bci.bundle import load_bundle  # noqa: E402
from bci.config import PreprocessingConfig  # noqa: E402
from bci.logging_setup import setup_logging  # noqa: E402
from bci.lsl_io import EEGReceiver  # noqa: E402
from bci.pipeline import InferencePipeline  # noqa: E402
from bci.preprocessing import Preprocessor  # noqa: E402
from bci.smoother import make_smoother  # noqa: E402

logger = logging.getLogger("bci.dev_realtime_log")


def measure_warmup(
    cfg: PreprocessingConfig,
    impulse_amp: float = 100.0,
    threshold_ratio: float = 0.01,
    chunk_samples: int = 16,
    max_seconds: float = 5.0,
) -> float:
    pre = Preprocessor(cfg)
    n_channels = cfg.n_channels
    pre.reset_filter_state(n_channels=n_channels)

    impulse = np.zeros((1, n_channels), dtype=np.float64)
    impulse[0, 0] = impulse_amp
    impulse_out = pre.transform_chunk(impulse)
    peak = float(np.abs(impulse_out).max())
    if peak == 0.0:
        raise RuntimeError("Impulse produced zero output; cannot measure decay")
    threshold = threshold_ratio * peak

    n_chunks = int(max_seconds * cfg.fs / chunk_samples)
    samples_after_impulse = 0
    for _ in range(n_chunks):
        zero_chunk = np.zeros((chunk_samples, n_channels), dtype=np.float64)
        out = pre.transform_chunk(zero_chunk)
        if float(np.abs(out).max()) < threshold:
            settle_time_s = (samples_after_impulse + chunk_samples) / cfg.fs
            return settle_time_s
        samples_after_impulse += chunk_samples
    return float("inf")


def _resolve_bundle_path(arg: str | None) -> Path | None:
    if arg is None:
        return None
    matches = sorted(glob.glob(arg))
    if not matches:
        raise FileNotFoundError(f"no bundle matched {arg!r}")
    return Path(matches[-1])


def run_realtime_loop(
    bundle_path: Path,
    channels: list[str] | None,
    warmup_s: float,
    stride_ms: int,
    duration_s: float,
) -> int:
    bundle = load_bundle(bundle_path)
    logger.info(
        "Loaded bundle %s (decoder=%s, label_map=%s, window=%d, channels=%s)",
        bundle_path,
        bundle.decoder_name,
        bundle.label_map,
        bundle.window_samples,
        bundle.preprocessing.channel_order,
    )

    rx = EEGReceiver(stream_type="EEG", channel_selection=channels)
    info = rx.connect()
    if info["n_channels"] != bundle.preprocessing.n_channels:
        raise RuntimeError(
            f"Bundle expects {bundle.preprocessing.n_channels} channels, "
            f"stream provides {info['n_channels']}. Use --channels to subset."
        )

    pre_cfg = PreprocessingConfig(
        fs=info["fs"],
        channel_order=info["channel_names"],
        bandpass=bundle.preprocessing.bandpass,
        bandpass_order=bundle.preprocessing.bandpass_order,
        notch_hz=bundle.preprocessing.notch_hz,
        notch_q=bundle.preprocessing.notch_q,
        reference=bundle.preprocessing.reference,
    )
    pre = Preprocessor(pre_cfg)
    smoother = make_smoother(bundle.smoother_name, bundle.smoother_params)
    pipeline = InferencePipeline(pre, bundle.decoder, smoother)

    rx.attach_preprocessor(pre)
    rx.start_streaming()
    logger.info("Streaming. warming up for %.2fs ...", warmup_s)
    t0 = time.time()
    while time.time() - t0 < warmup_s:
        if rx.is_stalled():
            logger.error("EEG stalled during warm-up")
            rx.stop_streaming()
            return 2
        time.sleep(0.05)
    logger.info("realtime_ready")

    stride_s = stride_ms / 1000.0
    next_t = time.time()
    end_t = time.time() + duration_s if duration_s > 0 else float("inf")
    stop = False

    def _on_signal(signum, frame):  # noqa: ANN001
        nonlocal stop
        stop = True
        logger.info("Caught signal %d", signum)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        while not stop and time.time() < end_t:
            if rx.is_stalled():
                logger.error("EEG stalled during streaming")
                return 3
            if rx.n_filled_filtered() < bundle.window_samples:
                time.sleep(0.01)
                continue
            window = rx.get_last_filtered(bundle.window_samples)
            proba = pipeline.predict_window(window)
            label_idx = int(np.argmax(proba))
            label = bundle.label_map.get(label_idx, str(label_idx))
            logger.info(
                "proba=%s -> %s",
                np.array2string(proba, precision=3, suppress_small=True),
                label,
            )
            next_t += stride_s
            sleep_for = next_t - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_t = time.time()
    finally:
        rx.stop_streaming()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--measure-warmup",
        action="store_true",
        help="Measure impulse decay and exit (no LSL or bundle needed)",
    )
    parser.add_argument(
        "--bundle",
        type=str,
        default=None,
        help="Glob/path to a .joblib bundle (default: latest under bundles/)",
    )
    parser.add_argument(
        "--channels",
        nargs="+",
        default=None,
        help="EEG channel names to subset (default: pull all 14)",
    )
    parser.add_argument(
        "--warmup-s", type=float, default=2.0, help="Warm-up wait before logging proba"
    )
    parser.add_argument(
        "--stride-ms", type=int, default=250, help="Inference cadence (ms)"
    )
    parser.add_argument(
        "--duration", type=float, default=0.0, help="0 = run until Ctrl-C"
    )
    parser.add_argument("--fs", type=float, default=128.0)
    parser.add_argument("--n-channels", type=int, default=2)
    args = parser.parse_args()

    setup_logging(REPO_ROOT / "logs", level="INFO")

    if args.measure_warmup:
        cfg = PreprocessingConfig(
            fs=args.fs,
            channel_order=[f"ch{i}" for i in range(args.n_channels)],
        )
        settle = measure_warmup(cfg)
        logger.info(
            "warm-up impulse settle time: %.3fs (use ~%.2fs default)",
            settle,
            min(2.0, settle + 0.5),
        )
        if settle == float("inf"):
            logger.error("Impulse did not settle within max_seconds")
            return 1
        return 0

    bundle_path = _resolve_bundle_path(
        args.bundle or str(REPO_ROOT / "bundles" / "*.joblib")
    )
    if bundle_path is None:
        logger.error("no bundle found; pass --bundle or train one first")
        return 1
    return run_realtime_loop(
        bundle_path=bundle_path,
        channels=args.channels,
        warmup_s=args.warmup_s,
        stride_ms=args.stride_ms,
        duration_s=args.duration,
    )


if __name__ == "__main__":
    raise SystemExit(main())
