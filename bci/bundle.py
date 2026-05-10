from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from .config import PreprocessingConfig
from .models.base import BaseDecoder

_TRACKED_PACKAGES = ("numpy", "scipy", "scikit-learn", "mne", "joblib", "pylsl")


def _pkg_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def collect_package_versions() -> dict[str, str]:
    versions = {pkg: _pkg_version(pkg) for pkg in _TRACKED_PACKAGES}
    versions["python"] = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    return versions


def _git_sha(cwd: str | Path | None = None) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(cwd) if cwd is not None else None,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    return "unknown"


@dataclass
class Bundle:
    decoder: BaseDecoder
    decoder_name: str
    decoder_params: dict[str, Any]
    preprocessing: PreprocessingConfig
    label_map: dict[int, str]
    window_samples: int
    stride_samples: int
    smoother_name: str
    smoother_params: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def make_metadata(
    *,
    subject: str,
    cal_acc: float,
    raw_data_path: str | Path | None,
    trial_len_s: float,
    cue_s: float,
    mi_s: float,
    rest_s: float,
    n_trials_per_class: int,
    fs: float,
    emotiv_n_channels: int,
    emotiv_total_channels: int,
    emotiv_channel_names: list[str],
    physical_electrodes: list[str],
    logical_channels: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    md: dict[str, Any] = {
        "subject": subject,
        "date": datetime.now(timezone.utc).isoformat(),
        "cal_acc": float(cal_acc),
        "raw_data_path": str(raw_data_path) if raw_data_path is not None else None,
        "trial_len_s": float(trial_len_s),
        "cue_s": float(cue_s),
        "mi_s": float(mi_s),
        "rest_s": float(rest_s),
        "n_trials_per_class": int(n_trials_per_class),
        "fs": float(fs),
        "emotiv_n_channels": int(emotiv_n_channels),
        "emotiv_total_channels": int(emotiv_total_channels),
        "emotiv_channel_names": list(emotiv_channel_names),
        "physical_electrodes": list(physical_electrodes),
        "logical_channels": list(logical_channels),
        "package_versions": collect_package_versions(),
        "git_sha": _git_sha(),
    }
    if extra:
        md.update(extra)
    return md


def save_bundle(bundle: Bundle, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "decoder": bundle.decoder,
        "decoder_name": bundle.decoder_name,
        "decoder_params": bundle.decoder_params,
        "preprocessing": asdict(bundle.preprocessing),
        "label_map": bundle.label_map,
        "window_samples": bundle.window_samples,
        "stride_samples": bundle.stride_samples,
        "smoother_name": bundle.smoother_name,
        # Init kwargs only — never the smoother instance, so internal
        # state (e.g. EMA running average) cannot accidentally be
        # persisted across runs.
        "smoother_params": bundle.smoother_params,
        "metadata": bundle.metadata,
    }
    joblib.dump(payload, path)
    return path


def load_bundle(path: str | Path) -> Bundle:
    payload = joblib.load(path)
    pre_dict = payload["preprocessing"]
    preprocessing = PreprocessingConfig(
        fs=pre_dict["fs"],
        channel_order=list(pre_dict["channel_order"]),
        bandpass=tuple(pre_dict["bandpass"]),
        bandpass_order=int(pre_dict["bandpass_order"]),
        notch_hz=pre_dict["notch_hz"],
        notch_q=float(pre_dict["notch_q"]),
        reference=str(pre_dict["reference"]),
    )
    return Bundle(
        decoder=payload["decoder"],
        decoder_name=payload["decoder_name"],
        decoder_params=dict(payload["decoder_params"]),
        preprocessing=preprocessing,
        label_map=dict(payload["label_map"]),
        window_samples=int(payload["window_samples"]),
        stride_samples=int(payload["stride_samples"]),
        smoother_name=str(payload["smoother_name"]),
        smoother_params=dict(payload["smoother_params"]),
        metadata=dict(payload["metadata"]),
    )
