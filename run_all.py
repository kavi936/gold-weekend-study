#!/usr/bin/env python3
"""End-to-end runner for the gold weekend curiosity study.

Phases:
  fetch     — download/cache raw series, print summary
  clean     — USD conversion + coverage table
  weekends  — build weekends.parquet + scaffold events.csv
  analysis  — Q1–Q5 + honesty checks
  report    — findings.md, figures, manipulation_test.md
  all       — fetch → clean → weekends → analysis → report
"""

from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import run_analysis
from src.calendar import build_weekend_index
from src.clean import run_clean
from src.config import load_config
from src.fetch import print_fetch_summary, run_fetch
from src.logging_utils import append_research_log, setup_logging
from src.report import write_reports
from src.weekends import run_weekends


def phase_fetch(cfg: dict, refresh: bool) -> dict:
    fetched = run_fetch(cfg, refresh=refresh)
    print_fetch_summary(fetched["info"])
    cache = cfg["paths"]["processed"] / "fetch_cache.pkl"
    with open(cache, "wb") as f:
        pickle.dump(fetched, f)
    print(f"Fetch cache → {cache}")
    return fetched


def _load_fetch(cfg: dict, refresh: bool) -> dict:
    cache = cfg["paths"]["processed"] / "fetch_cache.pkl"
    if cache.exists() and not refresh:
        with open(cache, "rb") as f:
            return pickle.load(f)
    return phase_fetch(cfg, refresh=refresh)


def phase_clean(cfg: dict, refresh: bool) -> dict:
    fetched = _load_fetch(cfg, refresh=False)
    weekends = build_weekend_index(cfg)
    cleaned = run_clean(cfg, fetched, weekends)
    cache = cfg["paths"]["processed"] / "clean_cache.pkl"
    with open(cache, "wb") as f:
        pickle.dump({"cleaned": cleaned, "fetched": fetched, "weekends": weekends}, f)
    print(
        f"Clean summary: {cleaned['n_dropped']} venue-weekends exceed "
        f">{100 * cfg['coverage_drop_threshold']:.0f}% missing "
        f"(see data/processed/coverage.csv)"
    )
    return cleaned


def _load_clean(cfg: dict) -> dict:
    cache = cfg["paths"]["processed"] / "clean_cache.pkl"
    if not cache.exists():
        raise FileNotFoundError("Run --phase clean first")
    with open(cache, "rb") as f:
        return pickle.load(f)


def phase_weekends(cfg: dict, refresh_gdelt: bool) -> None:
    bundle = _load_clean(cfg)
    panel, events = run_weekends(cfg, bundle["cleaned"], refresh_gdelt=refresh_gdelt)
    n_main = int(panel["included_main"].sum())
    n_study = int(panel["study_sample"].sum())
    print(
        f"Weekends panel: {len(panel)} rows | included_main={n_main} | "
        f"study_sample={n_study} | events={len(events)} → {cfg['paths']['events']}"
    )
    append_research_log(
        cfg["root"],
        f"- weekends.parquet rows={len(panel)}, included_main={n_main}, "
        f"dropped_coverage≈{(panel['excluded_reason']=='coverage_gt_5pct').sum()}",
    )


def phase_analysis(cfg: dict) -> dict:
    import pandas as pd

    panel_path = cfg["paths"]["processed"] / "weekends.parquet"
    if not panel_path.exists():
        raise FileNotFoundError("Run --phase weekends first")
    panel = pd.read_parquet(panel_path)
    cleaned = None
    fetched = None
    try:
        bundle = _load_clean(cfg)
        cleaned = bundle["cleaned"]
        fetched = bundle.get("fetched")
    except FileNotFoundError:
        pass
    results = run_analysis(cfg, panel, cleaned=cleaned)
    print(
        f"Analysis v2: {results['n_weekends']} weekends | "
        f"hit_rate={results['q2']['hit_rate']['hit_rate']:.3f} | "
        f"slope={results['q2']['slope']['slope']:.3f} | "
        f"stale_dropped={results.get('n_dropped_stale')}"
    )
    # Optional local-only diagnostic (not shipped in public tree)
    if fetched is not None:
        try:
            from src.outlier_audit import run_outlier_audit

            run_outlier_audit(cfg, fetched)
        except Exception as e:  # noqa: BLE001
            print(f"Outlier audit skipped: {e}")
    return results


def phase_report(cfg: dict) -> str:
    cache = cfg["paths"]["processed"] / "analysis_cache.pkl"
    if not cache.exists():
        raise FileNotFoundError("Run --phase analysis first")
    with open(cache, "rb") as f:
        results = pickle.load(f)
    md = write_reports(cfg, results)
    print(f"Reports → {cfg['paths']['reports']}")
    return md


def main() -> None:
    parser = argparse.ArgumentParser(description="Gold weekend curiosity study")
    parser.add_argument(
        "--phase",
        choices=["fetch", "clean", "weekends", "analysis", "report", "all"],
        default="fetch",
    )
    parser.add_argument("--refresh", action="store_true", help="Re-download raw caches")
    parser.add_argument("--refresh-gdelt", action="store_true", help="Re-query GDELT suggestions")
    args = parser.parse_args()

    logger = setup_logging()
    cfg = load_config()
    logger.info("Config loaded | study_end_date=%s", cfg.get("study_end_date"))

    if args.phase == "fetch":
        phase_fetch(cfg, args.refresh)
        return
    if args.phase == "clean":
        _load_fetch(cfg, args.refresh)
        phase_clean(cfg, args.refresh)
        return
    if args.phase == "weekends":
        phase_weekends(cfg, refresh_gdelt=args.refresh_gdelt)
        return
    if args.phase == "analysis":
        phase_analysis(cfg)
        return
    if args.phase == "report":
        print(phase_report(cfg))
        return
    if args.phase == "all":
        phase_fetch(cfg, args.refresh)
        phase_clean(cfg, False)
        phase_weekends(cfg, refresh_gdelt=args.refresh_gdelt)
        phase_analysis(cfg)
        print(phase_report(cfg))
        return


if __name__ == "__main__":
    main()
