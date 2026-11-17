"""Shared logging helpers for the study pipeline."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure study logger once and return it."""
    logger = logging.getLogger("gold_weekend_study")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def append_research_log(root, message: str) -> None:
    """Append a dated note to RESEARCH_LOG.md."""
    from datetime import date

    path = root / "RESEARCH_LOG.md"
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## {date.today().isoformat()}\n\n{message.rstrip()}\n")
