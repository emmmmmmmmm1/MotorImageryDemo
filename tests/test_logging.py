from __future__ import annotations

import logging
from pathlib import Path

from bci.logging_setup import setup_logging


def test_setup_logging_writes_to_file_and_stdout(tmp_path: Path, capsys) -> None:
    log_path = setup_logging(tmp_path, level="INFO")

    logger = logging.getLogger("bci.test")
    msg = "hello-from-test"
    logger.info(msg)

    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_path.exists()
    file_text = log_path.read_text(encoding="utf-8")
    assert msg in file_text

    captured = capsys.readouterr()
    assert msg in captured.err or msg in captured.out


def test_setup_logging_creates_dir(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "logs"
    log_path = setup_logging(nested)
    assert nested.is_dir()
    assert log_path.parent == nested
