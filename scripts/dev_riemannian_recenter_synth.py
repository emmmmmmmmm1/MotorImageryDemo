"""Riemannian recentering: cross-subject pre-training + new-subject calibration.

Demonstrates the Zanini et al. (2018) recentering approach:

  1. Simulate N_SOURCE synthetic subjects with varied signal profiles
     (different mu amplitudes and noise to induce inter-subject covariance
     variability — the key challenge recentering is designed to overcome).

  2. Offline pre-training: for each source subject estimate the Riemannian
     mean of their covariance matrices, recenter to the identity, pool all
     subjects, then train a shared MDM classifier.

  3. New-subject calibration: collect a small set of calibration trials,
     estimate the new subject's Riemannian mean, store as recentering ref.

  4. Evaluate on held-out test trials.  Reports both baseline accuracy
     (no recentering, source MDM applied directly) and recentered accuracy
     so the benefit of the alignment is visible.

  5. Save the calibrated bundle for use by the inference pipeline.

Run from the repo root:
    python scripts/dev_riemannian_recenter_synth.py [--n_source 5] [--seed 0]

References
----------
Zanini et al. (2018). Transfer Learning: A Riemannian Geometry Framework
With Applications to Brain-Computer Interfaces.
IEEE Trans Biomed Eng 65(5):1107-1116. DOI:10.1109/TBME.2017.2742501

Barachant et al. (2012). Multiclass Brain-Computer Interface Classification
by Riemannian Geometry. IEEE Trans Biomed Eng 59(4):920-928.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pyriemann.estimation import Covariances

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bci.bundle import Bundle, make_metadata, save_bundle  # noqa: E402
from bci.config import PreprocessingConfig, build_preprocessing_config, load_yaml  # noqa: E402
from bci.logging_setup import setup_logging  # noqa: E402
from bci.models.riemannian_recenter import RiemannianRecenterDecoder  # noqa: E402
from bci.preprocessing import Preprocessor  # noqa: E402
from tests._synth import generate_synthetic_mi  # noqa: E402

logger = logging.getLogger("bci.dev_riemannian_recenter_synth")

# Per-subject signal profiles (high_mu, low_mu, noise_amp).
# Varying amplitudes simulates inter-subject covariance spread —
# without recentering the source MDM class means don't generalise.
_PROFILES = [
    (8.0, 1.0, 1.2),
    (5.0, 0.5, 2.0),
    (10.0, 2.0, 1.0),
    (6.0, 1.5, 1.8),
    (7.0, 0.8, 1.5),
    (9.0, 1.2, 0.8),
    (4.0, 0.3, 2.5),
    (11.0, 3.0, 1.3),
]


def _subject_data(
    profile_idx: int,
    n_trials_per_class: int,
    fs: float,
    n_channels: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    high_mu, low_mu, noise_amp = _PROFILES[profile_idx % len(_PROFILES)]
    return generate_synthetic_mi(
        n_trials_per_class=n_trials_per_class,
        fs=fs,
        n_channels=n_channels,
        high_mu=high_mu,
        low_mu=low_mu,
        noise_amp=noise_amp,
        seed=seed,
    )


def _preprocess(X: np.ndarray, pre: Preprocessor) -> np.ndarray:
    """Apply offline filtering to a batch of trials (n_trials, n_ch, n_samples)."""
    return pre.transform(X.astype(np.float64))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n_source", type=int, default=5,
        help="Number of source subjects for offline pre-training (default: 5)"
    )
    parser.add_argument(
        "--n_trials_source", type=int, default=20,
        help="Trials per class per source subject (default: 20)"
    )
    parser.add_argument(
        "--n_trials_calib", type=int, default=10,
        help="Calibration trials per class for the new subject (default: 10)"
    )
    parser.add_argument(
        "--n_trials_test", type=int, default=20,
        help="Test trials per class for the new subject (default: 20)"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--config", default=str(REPO_ROOT / "configs" / "default.yaml")
    )
    args = parser.parse_args()

    setup_logging(REPO_ROOT / "logs", level="INFO")
    cfg = load_yaml(args.config)

    fs = 128.0
    n_channels = 2
    channel_order = ["C3", "C4"]
    pre_cfg: PreprocessingConfig = build_preprocessing_config(
        cfg, fs=fs, channel_order=channel_order
    )
    pre = Preprocessor(pre_cfg)

    win_cfg = cfg["windowing"]
    window_samples = int(round(float(win_cfg["window_s"]) * fs))
    stride_samples = int(round(int(win_cfg["calib_stride_ms"]) / 1000.0 * fs))

    rng = np.random.default_rng(args.seed)

    # ── Phase 1: offline pre-training on source subjects ──────────────
    logger.info(
        "=== Phase 1: offline pre-training — %d source subjects, "
        "%d trials/class each ===",
        args.n_source, args.n_trials_source,
    )

    Xs_source: list[np.ndarray] = []
    ys_source: list[np.ndarray] = []

    for s in range(args.n_source):
        seed_s = int(rng.integers(0, 2**31))
        X_s, y_s = _subject_data(s, args.n_trials_source, fs, n_channels, seed_s)
        X_s_filt = _preprocess(X_s, pre)
        Xs_source.append(X_s_filt)
        ys_source.append(y_s)
        logger.info(
            "  source subject %d: shape=%s, class_counts=%s",
            s, X_s.shape, np.bincount(y_s).tolist(),
        )

    decoder = RiemannianRecenterDecoder(metric="riemann", n_jobs=1)
    decoder.fit_source_subjects(Xs_source, ys_source)
    logger.info("Source MDM trained on pooled recentered covariances.")

    # ── Phase 2: new subject calibration ──────────────────────────────
    # Use a profile index beyond the source set so the new subject has
    # covariance structure not seen during offline training.
    new_profile = args.n_source
    seed_calib = int(rng.integers(0, 2**31))

    logger.info(
        "=== Phase 2: new subject calibration — %d trials/class ===",
        args.n_trials_calib,
    )
    X_calib, y_calib = _subject_data(
        new_profile, args.n_trials_calib, fs, n_channels, seed_calib
    )
    X_calib_filt = _preprocess(X_calib, pre)
    decoder.fit(X_calib_filt, y_calib)
    logger.info(
        "Recentering reference M_recenter computed from %d calibration trials.",
        len(y_calib),
    )

    # ── Phase 3: evaluate on held-out test data ────────────────────────
    seed_test = int(rng.integers(0, 2**31))
    logger.info(
        "=== Phase 3: test evaluation — %d trials/class ===",
        args.n_trials_test,
    )
    X_test, y_test = _subject_data(
        new_profile, args.n_trials_test, fs, n_channels, seed_test
    )
    X_test_filt = _preprocess(X_test, pre)

    # Baseline: source MDM applied directly (no recentering)
    C_test_raw = Covariances(estimator="oas").transform(X_test_filt.astype(np.float64))
    preds_baseline = decoder.mdm_.predict(C_test_raw)
    acc_baseline = float((preds_baseline == y_test).mean())

    # Recentered: map new subject's covariances into source space first
    preds_recentered = decoder.predict(X_test_filt)
    acc_recentered = float((preds_recentered == y_test).mean())

    logger.info("Baseline accuracy   (no recentering): %.3f", acc_baseline)
    logger.info("Recentered accuracy (Zanini 2018)    : %.3f", acc_recentered)
    logger.info("Improvement: %+.3f", acc_recentered - acc_baseline)

    # ── Save bundle ────────────────────────────────────────────────────
    ts_label = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_path = (
        REPO_ROOT / "bundles" / f"riemannian_recenter_new_subject_{ts_label}.joblib"
    )
    bundle = Bundle(
        decoder=decoder,
        decoder_name="riemannian_recenter",
        decoder_params=decoder.get_params(),
        preprocessing=pre_cfg,
        label_map={0: "left", 1: "right"},
        window_samples=window_samples,
        stride_samples=stride_samples,
        smoother_name="passthrough",
        smoother_params={},
        metadata=make_metadata(
            subject="new_subject_synth",
            cal_acc=acc_recentered,
            raw_data_path=None,
            trial_len_s=4.0,
            cue_s=1.0,
            mi_s=4.0,
            rest_s=2.0,
            n_trials_per_class=args.n_trials_calib,
            fs=fs,
            emotiv_n_channels=n_channels,
            emotiv_total_channels=7,
            emotiv_channel_names=["FC3", "FC4"],
            physical_electrodes=["FC3", "FC4"],
            logical_channels=channel_order,
            extra={
                "source": "synthetic_riemannian_recenter",
                "n_source_subjects": args.n_source,
                "n_trials_source": args.n_trials_source,
                "n_trials_calib": args.n_trials_calib,
                "acc_baseline_no_recenter": acc_baseline,
                "acc_recentered": acc_recentered,
                "seed": args.seed,
            },
        ),
    )
    save_bundle(bundle, bundle_path)
    logger.info("Bundle saved to %s", bundle_path)

    if acc_recentered < 0.65:
        logger.error("Recentered acc %.3f below 0.65 threshold", acc_recentered)
        return 1
    logger.info("OK: recentered acc %.3f >= 0.65", acc_recentered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
