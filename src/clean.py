"""USD conversion and coverage gates. Missing minutes stay NaN — never forward-filled."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.calendar import friday_close_utc, sunday_reopen_utc
from src.logging_utils import setup_logging


def token_close_usd_series(
    ohlc: pd.DataFrame,
    quote: str,
    stables: dict[str, pd.DataFrame],
) -> tuple[pd.Series, pd.Series, dict[str, float]]:
    """Convert token close series to USD using contemporaneous stablecoin rates.

    Returns (usd_close, volume, stats) where stats reports fallback usage.
    Fallback to rate=1.0 only when no stable print within 60 minutes.
    """
    empty_stats = {"n_minutes": 0, "n_fallback_1": 0, "pct_fallback_1": np.nan}
    if ohlc is None or ohlc.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), empty_stats
    close = ohlc["close"].astype(float)
    vol = ohlc["volume"].astype(float) if "volume" in ohlc.columns else pd.Series(0.0, index=close.index)
    if quote.upper() == "USD":
        return close, vol, {"n_minutes": int(len(close)), "n_fallback_1": 0, "pct_fallback_1": 0.0}

    key = "USDT" if quote.upper() == "USDT" else "USDC" if quote.upper() == "USDC" else None
    if key is None:
        raise ValueError(quote)
    stable = stables.get(key, pd.DataFrame())
    if stable is None or stable.empty or "close" not in getattr(stable, "columns", []):
        stats = {"n_minutes": int(len(close)), "n_fallback_1": int(len(close)), "pct_fallback_1": 1.0}
        return close * 1.0, vol, stats

    rate = stable["close"].reindex(close.index, method="ffill", tolerance=pd.Timedelta("60min"))
    fallback = rate.isna()
    rate = rate.fillna(1.0)
    stats = {
        "n_minutes": int(len(close)),
        "n_fallback_1": int(fallback.sum()),
        "pct_fallback_1": float(fallback.mean()) if len(close) else np.nan,
    }
    return close * rate, vol, stats


def weekend_expected_minutes(friday, cfg: dict[str, Any]) -> pd.DatetimeIndex:
    """1-min UTC index from Friday close to Sunday reopen inclusive."""
    start = friday_close_utc(friday, cfg)
    end = sunday_reopen_utc(friday, cfg)
    return pd.date_range(start=start, end=end, freq="1min", tz="UTC")


def coverage_for_weekend(
    series: pd.Series,
    friday,
    cfg: dict[str, Any],
) -> float:
    """Fraction of weekend minutes that have a non-NaN print (0..1). Missing = absent."""
    expected = weekend_expected_minutes(friday, cfg)
    if series is None or series.empty:
        return 0.0
    present = series.reindex(expected)
    return float(present.notna().mean())


def build_coverage_table(
    cfg: dict[str, Any],
    weekends: pd.DataFrame,
    token_usd: dict[str, pd.Series],
) -> pd.DataFrame:
    """Venue × symbol × weekend coverage; also aggregate % missing."""
    rows = []
    thr = float(cfg["coverage_drop_threshold"])
    for _, w in weekends.iterrows():
        fri = w["friday_date"]
        if isinstance(fri, pd.Timestamp):
            fri = fri.date()
        for v in cfg["venues"]:
            key = f"{v['venue']}:{v['symbol']}"
            series = token_usd.get(key, pd.Series(dtype=float))
            cov = coverage_for_weekend(series, fri, cfg)
            missing = 1.0 - cov
            rows.append(
                {
                    "weekend_id": w["weekend_id"],
                    "friday_date": fri,
                    "venue": v["venue"],
                    "token": v["token"],
                    "symbol": v["symbol"],
                    "pct_present": cov,
                    "pct_missing": missing,
                    "drop": missing > thr,
                }
            )
    return pd.DataFrame(rows)


def run_clean(cfg: dict[str, Any], fetched: dict[str, Any], weekends: pd.DataFrame) -> dict[str, Any]:
    """Convert tokens to USD and build coverage table."""
    logger = setup_logging()
    stables = fetched["stables"]
    token_usd: dict[str, pd.Series] = {}
    token_vol: dict[str, pd.Series] = {}
    usd_stats: dict[str, dict] = {}
    for v in cfg["venues"]:
        key = f"{v['venue']}:{v['symbol']}"
        ohlc = fetched["tokens"].get(key, pd.DataFrame())
        usd, vol, stats = token_close_usd_series(ohlc, v["quote"], stables)
        token_usd[key] = usd
        token_vol[key] = vol
        usd_stats[key] = stats
        logger.info(
            "USD series %s: %d points | rate=1.0 fallback %.2f%% (%d/%d)",
            key,
            usd.notna().sum(),
            100 * (stats["pct_fallback_1"] or 0),
            stats["n_fallback_1"],
            stats["n_minutes"],
        )

    # Aggregate fallback across USDT-quoted venues
    tot_n = sum(s["n_minutes"] for s in usd_stats.values())
    tot_fb = sum(s["n_fallback_1"] for s in usd_stats.values())
    pct_fb = (tot_fb / tot_n) if tot_n else np.nan
    logger.info("USDT/USDC conversion fallback overall: %.3f%% (%d / %d minutes)", 100 * pct_fb, tot_fb, tot_n)

    gold_close = fetched["gold"]["close"].astype(float) if not fetched["gold"].empty else pd.Series(dtype=float)
    gold_vol = (
        fetched["gold"]["volume"].astype(float)
        if (not fetched["gold"].empty and "volume" in fetched["gold"].columns)
        else pd.Series(dtype=float)
    )
    btc_close = fetched["btc"]["close"].astype(float) if not fetched["btc"].empty else pd.Series(dtype=float)
    gcf_close = fetched["gcf"]["close"].astype(float) if not fetched["gcf"].empty else pd.Series(dtype=float)

    coverage = build_coverage_table(cfg, weekends, token_usd)
    n_drop = int(coverage["drop"].sum())
    coverage_path = cfg["paths"]["processed"] / "coverage.csv"
    coverage.to_csv(coverage_path, index=False)
    logger.info(
        "Coverage table → %s (%d venue-weekends flagged >%.0f%% missing)",
        coverage_path,
        n_drop,
        100 * cfg["coverage_drop_threshold"],
    )

    return {
        "token_usd": token_usd,
        "token_vol": token_vol,
        "gold_usd": gold_close,
        "gold_vol": gold_vol,
        "gcf_usd": gcf_close,
        "btc_usd": btc_close,
        "coverage": coverage,
        "n_dropped": n_drop,
        "usd_fallback_stats": {"per_series": usd_stats, "pct_fallback_1": pct_fb, "n_fallback_1": tot_fb, "n_minutes": tot_n},
    }
