#!/usr/bin/env python3
"""Forward weekend L2 / liquidation recorder.

Separate from the descriptive study. Writes only to data/forward/.
Study analysis must never read this directory.

Usage:
  python record_weekends.py              # wait for Fri 16:00 ET → Mon 02:00 ET
  python record_weekends.py --once       # one snapshot cycle (for smoke test)
  python record_weekends.py --force      # record even outside the window
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_config
from src.logging_utils import setup_logging
from src.recorder import record_loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Record weekend L2 books + liquidations")
    parser.add_argument("--once", action="store_true", help="Single snapshot cycle then exit")
    parser.add_argument("--force", action="store_true", help="Record even outside Fri–Mon window")
    parser.add_argument("--max-seconds", type=float, default=None, help="Stop after N seconds (tests)")
    args = parser.parse_args()

    logger = setup_logging()
    cfg = load_config()
    if args.force:
        cfg["_force_record"] = True
    logger.info("Forward recorder → %s (study analysis does not read this)", cfg["paths"]["forward"])
    record_loop(cfg, once=args.once, max_seconds=args.max_seconds)


if __name__ == "__main__":
    main()
