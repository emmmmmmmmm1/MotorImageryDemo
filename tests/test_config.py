from __future__ import annotations

from pathlib import Path

import pytest

from bci.config import (
    PreprocessingConfig,
    build_preprocessing_config,
    load_yaml,
)


def test_apply_car_off_for_2ch_auto() -> None:
    cfg = PreprocessingConfig(fs=128, channel_order=["C3", "C4"])
    assert cfg.reference == "auto"
    assert cfg.apply_car is False
    assert cfg.n_channels == 2


def test_apply_car_on_for_4ch_auto() -> None:
    cfg = PreprocessingConfig(
        fs=128, channel_order=["C3", "C4", "Cz", "C5"]
    )
    assert cfg.apply_car is True


def test_apply_car_explicit_overrides() -> None:
    cfg2 = PreprocessingConfig(fs=128, channel_order=["C3", "C4"], reference="car")
    assert cfg2.apply_car is True
    cfg4 = PreprocessingConfig(
        fs=128, channel_order=["C3", "C4", "Cz", "C5"], reference="none"
    )
    assert cfg4.apply_car is False


def test_invalid_reference_raises() -> None:
    with pytest.raises(ValueError):
        PreprocessingConfig(fs=128, channel_order=["C3"], reference="bogus")


def test_invalid_bandpass_raises() -> None:
    with pytest.raises(ValueError):
        PreprocessingConfig(
            fs=128, channel_order=["C3"], bandpass=(30.0, 8.0)
        )


def test_load_yaml_default(tmp_path: Path) -> None:
    repo_default = Path(__file__).resolve().parents[1] / "configs" / "default.yaml"
    d = load_yaml(repo_default)
    assert "preprocessing" in d
    assert d["preprocessing"]["reference"] == "auto"
    assert d["windowing"]["window_s"] == 2.0


def test_build_preprocessing_config_from_yaml() -> None:
    repo_default = Path(__file__).resolve().parents[1] / "configs" / "default.yaml"
    d = load_yaml(repo_default)
    cfg = build_preprocessing_config(d, fs=128.0, channel_order=["C3", "C4"])
    assert cfg.fs == 128.0
    assert cfg.bandpass == (8.0, 30.0)
    assert cfg.bandpass_order == 4
    assert cfg.notch_hz == 50.0
    assert cfg.reference == "auto"
    assert cfg.apply_car is False
