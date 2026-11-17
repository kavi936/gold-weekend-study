"""Build the reusable weekend panel + scaffold events.csv."""

from __future__ import annotations

from datetime import date, datetime, timedelta, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from src.calendar import (
    ET,
    build_weekend_index,
    et_to_utc,
    friday_close_utc,
    post_open_utc,
    pre_open_utc,
    saturday_noon_utc,
    sunday_reopen_utc,
)
from src.logging_utils import setup_logging
from src.math_defs import (
    dislocation,
    last_trade_age_min,
    median_window_price,
    price_at,
    simple_return,
    volume_at,
    weekday_median_basis,
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "gold-weekend-study/1.0 (research)"})


def _as_date(v) -> date:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    return pd.Timestamp(v).date()


def btc_weekend_return(btc: pd.Series, friday: date, cfg: dict[str, Any]) -> float:
    t0 = pd.Timestamp(friday_close_utc(friday, cfg))
    t1 = pd.Timestamp(pre_open_utc(friday, cfg))
    p0 = price_at(btc, t0, tolerance_min=5)
    p1 = price_at(btc, t1, tolerance_min=5)
    return simple_return(p1, p0)


def thursday_to_friday_token_move(series: pd.Series, friday: date, cfg: dict[str, Any]) -> float:
    """Weekday placebo: Thursday 17:00 ET → Friday 16:00 ET token return (gold is open)."""
    thu = friday - timedelta(days=1)
    t0 = pd.Timestamp(et_to_utc(datetime.combine(thu, time(17, 0), tzinfo=ET)))
    t1 = pd.Timestamp(et_to_utc(datetime.combine(friday, time(16, 0), tzinfo=ET)))
    win = int(cfg.get("snapshot_window_min", 5))
    p0 = median_window_price(series, t0, win)
    p1 = median_window_price(series, t1, win)
    return simple_return(p1, p0)


def suggest_gdelt_label(friday: date, cfg: dict[str, Any], retries: int = 4) -> tuple[str, int]:
    """Return (suggested_label, article_count). Failed lookup → ('unknown', -1), never 'quiet'.

    Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
    """
    import time as _time

    logger = setup_logging()
    sat = friday + timedelta(days=1)
    sun = friday + timedelta(days=2)
    start = sat.strftime("%Y%m%d000000")
    end = sun.strftime("%Y%m%d235959")
    params = {
        "query": cfg["gdelt"]["query"],
        "mode": "ArtList",
        "maxrecords": 250,
        "format": "json",
        "startdatetime": start,
        "enddatetime": end,
    }
    last_err = None
    for attempt in range(retries):
        try:
            r = SESSION.get(cfg["gdelt"]["doc_api"], params=params, timeout=25)
            if r.status_code == 429:
                _time.sleep(2.0 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            arts = data.get("articles") or []
            n = len(arts)
            thr = int(cfg["gdelt"]["news_count_threshold"])
            return ("news" if n >= thr else "quiet"), n
        except Exception as e:  # noqa: BLE001
            last_err = e
            _time.sleep(1.5 * (attempt + 1))
    logger.warning("GDELT failed for %s after retries: %s — label=unknown", friday, last_err)
    return "unknown", -1


def scaffold_events_csv(cfg: dict[str, Any], weekends: pd.DataFrame, refresh_suggestions: bool = False) -> pd.DataFrame:
    """One row per weekend. Preserve hand-confirmed labels if file already exists."""
    import time as _time

    logger = setup_logging()
    path: Path = cfg["paths"]["events"]
    existing = None
    if path.exists():
        existing = pd.read_csv(path)
        if "weekend_id" in existing.columns:
            existing = existing.set_index("weekend_id")

    need_gdelt: list[tuple[str, date]] = []
    base_rows: dict[str, dict] = {}
    for _, w in weekends.iterrows():
        wid = w["weekend_id"]
        fri = _as_date(w["friday_date"])
        prev_label = prev_cat = prev_url = prev_conf = prev_sug = ""
        prev_count: Any = ""
        if existing is not None and wid in existing.index:
            row = existing.loc[wid]
            prev_label = "" if pd.isna(row.get("label", "")) else str(row.get("label", ""))
            prev_cat = "" if pd.isna(row.get("catalyst", "")) else str(row.get("catalyst", ""))
            prev_url = "" if pd.isna(row.get("source_url", "")) else str(row.get("source_url", ""))
            prev_conf = "" if pd.isna(row.get("confidence", "")) else str(row.get("confidence", ""))
            prev_sug = "" if pd.isna(row.get("label_suggested", "")) else str(row.get("label_suggested", ""))
            prev_count = row.get("gdelt_count", "")
        # Migrate old failed defaults: quiet with gdelt_count=-1 → unknown
        if prev_sug == "quiet" and (prev_count == -1 or prev_count == "-1"):
            prev_sug = "unknown"
        base_rows[wid] = {
            "weekend_id": wid,
            "friday_date": fri.isoformat(),
            "label": prev_label,
            "label_suggested": prev_sug,
            "gdelt_count": prev_count,
            "catalyst": prev_cat,
            "source_url": prev_url,
            "confidence": prev_conf,
            "_fri": fri,
        }
        # Re-query unknowns only on explicit --refresh-gdelt (avoid 429 storms).
        if refresh_suggestions or not prev_sug:
            need_gdelt.append((wid, fri))

    if need_gdelt:
        logger.info("GDELT suggestions for %d weekends (sequential + backoff)", len(need_gdelt))
        for wid, fri in need_gdelt:
            sug, count = suggest_gdelt_label(fri, cfg)
            base_rows[wid]["label_suggested"] = sug
            base_rows[wid]["gdelt_count"] = count
            _time.sleep(1.0)

    rows = []
    for wid in [w["weekend_id"] for _, w in weekends.iterrows()]:
        r = dict(base_rows[wid])
        r.pop("_fri", None)
        rows.append(r)
    events = pd.DataFrame(rows)
    events.to_csv(path, index=False)
    return events


def _snap(
    series: pd.Series,
    vol: pd.Series,
    ts: pd.Timestamp,
    cfg: dict[str, Any],
    *,
    pre_open_window: bool = False,
    reopen_ts: pd.Timestamp | None = None,
) -> dict[str, float]:
    """Median-window price + point price + trade age + volume at snapshot."""
    win = int(cfg.get("snapshot_window_min", 5))
    stale_max = float(cfg.get("stale_trade_max_min", 10))
    if pre_open_window and reopen_ts is not None:
        # 10 minutes before reopen−5 → [reopen−15, reopen−5]
        end = pd.Timestamp(reopen_ts) - pd.Timedelta(minutes=int(cfg.get("pre_open_offset_min", 5)))
        start = end - pd.Timedelta(minutes=10)
        med = median_window_price(series, ts, win, start=start, end=end)
    else:
        med = median_window_price(series, ts, win)
    pt = price_at(series, ts, tolerance_min=2)
    age = last_trade_age_min(vol, ts) if vol is not None and len(vol) else np.nan
    v = volume_at(vol, ts) if vol is not None and len(vol) else np.nan
    stale = bool(np.isnan(age) or age > stale_max)
    return {"median": med, "point": pt, "age_min": age, "volume": v, "stale": stale}


def build_weekend_panel(
    cfg: dict[str, Any],
    weekends: pd.DataFrame,
    cleaned: dict[str, Any],
    events: pd.DataFrame,
) -> pd.DataFrame:
    """One row per weekend × token × venue with all measured quantities (v2)."""
    logger = setup_logging()
    gold = cleaned["gold_usd"]
    gold_vol = cleaned.get("gold_vol", pd.Series(dtype=float))
    gcf = cleaned["gcf_usd"]
    btc = cleaned["btc_usd"]
    coverage = cleaned["coverage"]
    token_vol = cleaned.get("token_vol", {})
    thr = float(cfg["coverage_drop_threshold"])
    crash_thr = float(cfg["crypto_crash_btc_return"])
    events_ix = events.set_index("weekend_id") if "weekend_id" in events.columns else events
    win = int(cfg.get("snapshot_window_min", 5))

    rows: list[dict[str, Any]] = []
    n_stale = 0
    for _, w in weekends.iterrows():
        fri = _as_date(w["friday_date"])
        wid = w["weekend_id"]
        t_fri = pd.Timestamp(friday_close_utc(fri, cfg))
        t_pre = pd.Timestamp(pre_open_utc(fri, cfg))
        t_reopen = pd.Timestamp(sunday_reopen_utc(fri, cfg))

        g_fri = median_window_price(gold, t_fri, win)
        g5 = median_window_price(gold, pd.Timestamp(post_open_utc(fri, cfg, minutes=5)), win)
        g15 = median_window_price(gold, pd.Timestamp(post_open_utc(fri, cfg, minutes=15)), win)
        g60 = median_window_price(gold, pd.Timestamp(post_open_utc(fri, cfg, minutes=60)), win)
        g_fri_gcf = price_at(gcf, t_fri, tolerance_min=60) if not gcf.empty else np.nan
        g15_gcf = (
            price_at(gcf, pd.Timestamp(post_open_utc(fri, cfg, minutes=15)), tolerance_min=60)
            if not gcf.empty
            else np.nan
        )
        # Monday gold levels for Link 3 / gap-fill (exploratory consumers)
        mon = fri + timedelta(days=3)
        g_mon_03 = median_window_price(
            gold, pd.Timestamp(et_to_utc(datetime.combine(mon, time(3, 0), tzinfo=ET))), win
        )
        g_mon_0530 = median_window_price(
            gold, pd.Timestamp(et_to_utc(datetime.combine(mon, time(5, 30), tzinfo=ET))), win
        )  # ~10:30 London in winter ≈ 05:30 ET
        g_mon_17 = median_window_price(
            gold, pd.Timestamp(et_to_utc(datetime.combine(mon, time(17, 0), tzinfo=ET))), win
        )

        btc_ret = btc_weekend_return(btc, fri, cfg)
        crypto_crash = bool(btc_ret < crash_thr) if not np.isnan(btc_ret) else False

        ev = events_ix.loc[wid] if wid in events_ix.index else None
        label = label_sug = catalyst = source_url = confidence = ""
        if ev is not None:
            label = str(ev.get("label", "") or "")
            label_sug = str(ev.get("label_suggested", "") or "")
            catalyst = str(ev.get("catalyst", "") or "")
            source_url = str(ev.get("source_url", "") or "")
            confidence = str(ev.get("confidence", "") or "")
        label_confirmed = label if label in ("news", "quiet") else ""
        if label_confirmed:
            effective_label = label_confirmed
            label_provisional = False
        else:
            effective_label = label_sug if label_sug in ("news", "quiet", "unknown") else "unknown"
            label_provisional = True

        study_end = cfg.get("study_end_date")
        study_sample = True if not study_end else fri <= date.fromisoformat(str(study_end))

        for v in cfg["venues"]:
            key = f"{v['venue']}:{v['symbol']}"
            series = cleaned["token_usd"].get(key, pd.Series(dtype=float))
            vol = token_vol.get(key, pd.Series(dtype=float))
            cov_row = coverage[
                (coverage["weekend_id"] == wid)
                & (coverage["venue"] == v["venue"])
                & (coverage["symbol"] == v["symbol"])
            ]
            pct_missing = float(cov_row["pct_missing"].iloc[0]) if not cov_row.empty else 1.0
            drop_cov = pct_missing > thr
            holiday = bool(w["holiday_weekend"])

            s_fri = _snap(series, vol, t_fri, cfg)
            s_pre = _snap(series, vol, t_pre, cfg, pre_open_window=True, reopen_ts=t_reopen)
            s_1h = _snap(series, vol, pd.Timestamp(post_open_utc(fri, cfg, hours=1)), cfg)
            s_4h = _snap(series, vol, pd.Timestamp(post_open_utc(fri, cfg, hours=4)), cfg)

            any_stale = bool(s_fri["stale"] or s_pre["stale"] or s_1h["stale"] or s_4h["stale"])
            if any_stale:
                n_stale += 1

            excluded_reason = ""
            included_main = True
            if holiday:
                included_main = False
                excluded_reason = "holiday_weekend"
            elif drop_cov:
                included_main = False
                excluded_reason = "coverage_gt_5pct"
            elif any_stale:
                included_main = False
                excluded_reason = "stale_snapshot"

            t_fri_px = s_fri["median"]
            t_pre_px = s_pre["median"]
            t_1h = s_1h["median"]
            t_4h = s_4h["median"]

            b_weekday = weekday_median_basis(
                series, gold, pd.Timestamp(t_fri), n_weekdays=int(cfg["normal_basis_lookback_weekdays"])
            )
            d = dislocation(t_pre_px, g_fri, b_weekday)
            w_move = simple_return(t_pre_px, t_fri_px)
            # Point-price sensitivity (old definition)
            w_point = simple_return(s_pre["point"], s_fri["point"])
            d_point = dislocation(s_pre["point"], price_at(gold, t_fri, 2), b_weekday)

            gap5 = simple_return(g5, g_fri)
            gap15 = simple_return(g15, g_fri)
            gap60 = simple_return(g60, g_fri)
            gap15_gcf = simple_return(g15_gcf, g_fri_gcf)
            r1 = simple_return(t_1h, t_pre_px)
            r4 = simple_return(t_4h, t_pre_px)

            # Partial-weekend signal (Fri → Sat noon) — NOT a placebo
            t_sat_noon = pd.Timestamp(saturday_noon_utc(fri))
            t_sat = median_window_price(series, t_sat_noon, win)
            w_sat = simple_return(t_sat, t_fri_px)
            # Also Sun 00:00 and Sun 12:00 for time-of-information (exploratory)
            sun = fri + timedelta(days=2)
            t_sun_00 = median_window_price(
                series, pd.Timestamp(et_to_utc(datetime.combine(sun, time(0, 0), tzinfo=ET))), win
            )
            t_sun_12 = median_window_price(
                series, pd.Timestamp(et_to_utc(datetime.combine(sun, time(12, 0), tzinfo=ET))), win
            )
            w_sun_00 = simple_return(t_sun_00, t_fri_px)
            w_sun_12 = simple_return(t_sun_12, t_fri_px)

            w_weekday = thursday_to_friday_token_move(series, fri, cfg)

            rows.append(
                {
                    "weekend_id": wid,
                    "friday_date": fri.isoformat(),
                    "token": v["token"],
                    "venue": v["venue"],
                    "symbol": v["symbol"],
                    "holiday_weekend": holiday,
                    "included_main": included_main,
                    "excluded_reason": excluded_reason,
                    "pct_missing_weekend_minutes": pct_missing,
                    "study_sample": study_sample,
                    "regime": w["regime"],
                    "stale_any": any_stale,
                    "T_fri_age_min": s_fri["age_min"],
                    "T_pre_age_min": s_pre["age_min"],
                    "T_post_1h_age_min": s_1h["age_min"],
                    "T_post_4h_age_min": s_4h["age_min"],
                    "T_fri_volume": s_fri["volume"],
                    "T_pre_volume": s_pre["volume"],
                    "G_fri": g_fri,
                    "T_fri": t_fri_px,
                    "T_pre": t_pre_px,
                    "G_open_5": g5,
                    "G_open_15": g15,
                    "G_open_60": g60,
                    "T_post_1h": t_1h,
                    "T_post_4h": t_4h,
                    "T_fri_point": s_fri["point"],
                    "T_pre_point": s_pre["point"],
                    "G_fri_gcf": g_fri_gcf,
                    "G_open_15_gcf": g15_gcf,
                    "G_mon_03et": g_mon_03,
                    "G_mon_0530et": g_mon_0530,
                    "G_mon_17et": g_mon_17,
                    "B_weekday": b_weekday,
                    "D": d,
                    "D_point": d_point,
                    "W": w_move,
                    "W_point": w_point,
                    "Gap_5": gap5,
                    "Gap_15": gap15,
                    "Gap_60": gap60,
                    "Gap_15_gcf": gap15_gcf,
                    "W_partial_sat_noon": w_sat,
                    "W_sun_00": w_sun_00,
                    "W_sun_12": w_sun_12,
                    "W_weekday_placebo": w_weekday,
                    "R_1h": r1,
                    "R_4h": r4,
                    "btc_weekend_return": btc_ret,
                    "crypto_crash": crypto_crash,
                    "label": effective_label,
                    "label_confirmed": label_confirmed,
                    "label_suggested": label_sug,
                    "label_provisional": label_provisional,
                    "catalyst": catalyst,
                    "source_url": source_url,
                    "confidence": confidence,
                }
            )

    panel = pd.DataFrame(rows)
    out = cfg["paths"]["processed"] / "weekends.parquet"
    panel.to_parquet(out, index=False)
    logger.info(
        "Wrote %s (%d rows, %d included_main, %d study_sample, stale_flagged_rows=%d)",
        out,
        len(panel),
        int(panel["included_main"].sum()),
        int(panel["study_sample"].sum()),
        n_stale,
    )
    # Stale drop summary by venue
    stale_rows = panel.loc[panel["excluded_reason"] == "stale_snapshot"]
    if len(stale_rows):
        logger.info("Stale exclusions by venue:\n%s", stale_rows.groupby("venue").size().to_string())
    return panel


def run_weekends(cfg: dict[str, Any], cleaned: dict[str, Any], refresh_gdelt: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekends = build_weekend_index(cfg)
    events = scaffold_events_csv(cfg, weekends, refresh_suggestions=refresh_gdelt)
    panel = build_weekend_panel(cfg, weekends, cleaned, events)
    return panel, events
