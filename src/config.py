"""Load study configuration from YAML and environment."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load config.yaml and resolve absolute data/report paths."""
    load_dotenv(ROOT / ".env")
    path = config_path or (ROOT / "config.yaml")
    with open(path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    for key in ("raw", "processed", "reports", "figures", "forward"):
        p = Path(cfg["paths"][key])
        if not p.is_absolute():
            p = ROOT / p
        cfg["paths"][key] = p
        p.mkdir(parents=True, exist_ok=True)

    events = Path(cfg["paths"]["events"])
    if not events.is_absolute():
        events = ROOT / events
    cfg["paths"]["events"] = events
    events.parent.mkdir(parents=True, exist_ok=True)

    cfg["root"] = ROOT
    return cfg
