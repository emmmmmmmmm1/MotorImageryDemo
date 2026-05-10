"""Publish calibration Markers over LSL, paced like Unity.

Use alongside ``python -m apps.service`` and an EEG outlet:

    python scripts/dev_fake_markers.py
    python scripts/dev_fake_markers.py --trials-per-class 2 --subject-check

The stream publishes left/right cue labels (0/1) followed by rest (99).
Only cue labels count toward service calibration progress; rest markers
are still emitted so the wire protocol matches the Unity-side sequence.
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

logger = logging.getLogger("bci.dev_fake_markers")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials-per-class", type=int, default=20)
    parser.add_argument("--cue-s", type=float, default=1.0)
    parser.add_argument("--mi-s", type=float, default=4.0)
    parser.add_argument("--rest-s", type=float, default=2.0)
    parser.add_argument("--left-label", type=int, default=0)
    parser.add_argument("--right-label", type=int, default=1)
    parser.add_argument("--rest-label", type=int, default=99)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--name", default="FakeMarkers")
    parser.add_argument("--source-id", default="fake_markers")
    args = parser.parse_args()

    setup_logging(REPO_ROOT / "logs", level="INFO")
    info = StreamInfo(
        name=args.name,
        type="Markers",
        channel_count=1,
        nominal_srate=0.0,
        channel_format="int32",
        source_id=args.source_id,
    )
    outlet = StreamOutlet(info)

    labels = [args.left_label] * args.trials_per_class
    labels += [args.right_label] * args.trials_per_class
    rng = np.random.default_rng(args.seed)
    rng.shuffle(labels)

    stop = False

    def _on_signal(signum, frame):  # noqa: ANN001
        nonlocal stop
        stop = True
        logger.info("Caught signal %d, stopping", signum)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    logger.info(
        "Publishing %d cue markers + rest markers (cue=%.2fs, mi=%.2fs, rest=%.2fs)",
        len(labels),
        args.cue_s,
        args.mi_s,
        args.rest_s,
    )
    time.sleep(args.cue_s)
    for idx, label in enumerate(labels, start=1):
        if stop:
            break
        t_cue = local_clock()
        outlet.push_sample([int(label)], t_cue)
        logger.info("cue %d/%d label=%d t_lsl=%.6f", idx, len(labels), label, t_cue)
        time.sleep(args.mi_s)
        t_rest = local_clock()
        outlet.push_sample([int(args.rest_label)], t_rest)
        logger.info("rest label=%d t_lsl=%.6f", args.rest_label, t_rest)
        time.sleep(args.rest_s + args.cue_s)

    logger.info("Done publishing markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
