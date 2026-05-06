from __future__ import annotations

import logging
import logging.config
from pathlib import Path

_DEFAULT_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    log_dir: str | Path,
    level: str = "INFO",
    filename: str = "service.log",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
) -> Path:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / filename

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {"format": _DEFAULT_FMT, "datefmt": _DEFAULT_DATEFMT},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "level": level,
                    "filename": str(log_path),
                    "maxBytes": max_bytes,
                    "backupCount": backup_count,
                    "encoding": "utf-8",
                },
            },
            "root": {"level": level, "handlers": ["console", "file"]},
        }
    )
    return log_path
