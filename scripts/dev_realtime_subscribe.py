"""Subscribe to Phase 5 Status and BCI_Proba streams.

Useful for checking realtime warm-up timing:

    python scripts/dev_realtime_subscribe.py --duration 10

The script logs Status messages and probability vectors with local
arrival times. It exits non-zero if neither stream produces data.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
from pylsl import StreamInlet, resolve_byprop

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bci.logging_setup import setup_logging  # noqa: E402

logger = logging.getLogger("bci.dev_realtime_subscribe")


def _resolve_inlet(stream_type: str, timeout_s: float) -> StreamInlet:
    streams = resolve_byprop("type", stream_type, timeout=timeout_s)
    if not streams:
        raise RuntimeError(f"No LSL stream type={stream_type!r} found")
    inlet = StreamInlet(streams[0])
    inlet.open_stream(timeout=2.0)
    logger.info(
        "Resolved %s name=%s source_id=%s",
        stream_type,
        streams[0].name(),
        streams[0].source_id(),
    )
    return inlet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=0.0, help="0 = run until Ctrl-C")
    parser.add_argument("--resolve-timeout", type=float, default=5.0)
    args = parser.parse_args()

    setup_logging(REPO_ROOT / "logs", level="INFO")
    status_in = _resolve_inlet("Status", args.resolve_timeout)
    proba_in = _resolve_inlet("BCI_Proba", args.resolve_timeout)

    t0 = time.time()
    n_status = 0
    n_proba = 0
    try:
        while args.duration <= 0 or (time.time() - t0) < args.duration:
            status_samples, status_ts = status_in.pull_chunk(
                timeout=0.0, max_samples=64
            )
            for sample, t_lsl in zip(status_samples, status_ts):
                n_status += 1
                logger.info("status t_lsl=%.6f msg=%s", float(t_lsl), sample[0])

            proba_samples, proba_ts = proba_in.pull_chunk(
                timeout=0.0, max_samples=64
            )
            for sample, t_lsl in zip(proba_samples, proba_ts):
                n_proba += 1
                arr = np.asarray(sample, dtype=np.float64)
                logger.info(
                    "proba t_lsl=%.6f p=%s",
                    float(t_lsl),
                    np.array2string(arr, precision=3, suppress_small=True),
                )
            time.sleep(0.02)
    except KeyboardInterrupt:
        logger.info("Interrupted")

    logger.info("summary: status=%d proba=%d", n_status, n_proba)
    return 0 if (n_status + n_proba) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
