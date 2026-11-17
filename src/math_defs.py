"""Basis / gap math — pure functions, unit-tested.

Assumptions: all token and gold prices are already in USD.
Missing inputs stay NaN; we never invent or forward-fill here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def to_usd(price: float | pd.Series, quote: str, usdt_usd: float | pd.Series = 1.0, usdc_usd: float | pd.Series = 1.0):
    """Convert a quote-currency price to USD.

    quote USD → unchanged; USDT → * usdt_usd; USDC → * usdc_usd.
    """
    q = quote.upper()
    if q == "USD":
        return price
    if q == "USDT":
        return price * usdt_usd
    if q == "USDC":
        return price * usdc_usd
    raise ValueError(f"Unsupported quote currency: {quote}")


def basis(token_usd: float, gold_usd: float) -> float:
    """(T/G − 1). Returns NaN if gold is 0/NaN."""
    if gold_usd is None or (isinstance(gold_usd, float) and (np.isnan(gold_usd) or gold_usd == 0)):
        return np.nan
    if token_usd is None or (isinstance(token_usd, float) and np.isnan(token_usd)):
        return np.nan
    return float(token_usd) / float(gold_usd) - 1.0


def simple_return(end: float, start: float) -> float:
    """end/start − 1."""
    if start is None or end is None:
        return np.nan
    if isinstance(start, float) and (np.isnan(start) or start == 0):
        return np.nan
    if isinstance(end, float) and np.isnan(end):
        return np.nan
    return float(end) / float(start) - 1.0


def dislocation(t_pre: float, g_fri: float, b_weekday: float) -> float:
    """D = (T_pre/G_fri − 1) − B_weekday."""
    raw = basis(t_pre, g_fri)
    if np.isnan(raw) or b_weekday is None or (isinstance(b_weekday, float) and np.isnan(b_weekday)):
        return np.nan
    return raw - float(b_weekday)


def convergence_shares(d: float, gap: float, r_post: float) -> tuple[float, float]:
    """Gold share = Gap/D; token share = −R/D.

    When D is near 0, returns (NaN, NaN). Shares may fall outside [0,1]
    when both legs move the 'wrong' way — callers should annotate that.
    """
    if d is None or (isinstance(d, float) and (np.isnan(d) or abs(d) < 1e-12)):
        return np.nan, np.nan
    gold_share = float(gap) / float(d)
    token_share = -float(r_post) / float(d)
    return gold_share, token_share


def same_sign(a: float, b: float) -> bool | float:
    """True if a and b have the same strict sign; NaN if either is 0/NaN."""
    if a is None or b is None:
        return np.nan
    if isinstance(a, float) and (np.isnan(a) or a == 0):
        return np.nan
    if isinstance(b, float) and (np.isnan(b) or b == 0):
        return np.nan
    return (a > 0 and b > 0) or (a < 0 and b < 0)


def weekday_median_basis(
    token_series: pd.Series,
    gold_series: pd.Series,
    friday: pd.Timestamp,
    n_weekdays: int = 5,
) -> float:
    """Median (T/G−1) over the prior n_weekdays Mon–Fri closes before this Friday.

    Expects minute-indexed UTC Series. Uses each weekday's 17:00 ET bar when present,
    else the last available bar that calendar day in ET.
    """
    from datetime import datetime, time, timedelta
    from zoneinfo import ZoneInfo

    ET = ZoneInfo("America/New_York")
    if token_series is None or gold_series is None:
        return np.nan
    if len(token_series) == 0 or len(gold_series) == 0:
        return np.nan
    if not isinstance(token_series.index, pd.DatetimeIndex) or not isinstance(
        gold_series.index, pd.DatetimeIndex
    ):
        return np.nan

    if not isinstance(friday, pd.Timestamp):
        friday = pd.Timestamp(friday)
    if friday.tzinfo is None:
        friday = friday.tz_localize("UTC")

    bases: list[float] = []
    d = friday.tz_convert(ET).date()
    checked = 0
    guard = 0
    while checked < n_weekdays and guard < 20:
        guard += 1
        d = d - timedelta(days=1)
        if d.weekday() >= 5:  # skip Sat/Sun
            continue
        # Prefer 17:00 ET that day
        target_et = datetime.combine(d, time(17, 0), tzinfo=ET)
        target_utc = pd.Timestamp(target_et.astimezone(ZoneInfo("UTC")))
        day_start = pd.Timestamp(datetime.combine(d, time(0, 0), tzinfo=ET).astimezone(ZoneInfo("UTC")))
        day_end = day_start + pd.Timedelta(days=1)
        t_day = token_series.loc[(token_series.index >= day_start) & (token_series.index < day_end)]
        g_day = gold_series.loc[(gold_series.index >= day_start) & (gold_series.index < day_end)]
        if t_day.empty or g_day.empty:
            checked += 1  # count attempted weekday even if missing → NaN contribution skipped
            continue
        t_px = _nearest_or_last(t_day, target_utc)
        g_px = _nearest_or_last(g_day, target_utc)
        b = basis(t_px, g_px)
        if not np.isnan(b):
            bases.append(b)
        checked += 1
    if not bases:
        return np.nan
    return float(np.median(bases))


def _nearest_or_last(series: pd.Series, target: pd.Timestamp) -> float:
    if target in series.index:
        return float(series.loc[target])
    # last bar at or before target on that day
    prior = series.loc[series.index <= target]
    if not prior.empty:
        return float(prior.iloc[-1])
    return float(series.iloc[-1])


def _ensure_utc_ts(ts: pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def price_at(series: pd.Series, ts: pd.Timestamp, tolerance_min: int = 2) -> float:
    """Exact minute match, else nearest within tolerance; else NaN (no silent fill across gaps)."""
    if series is None or series.empty:
        return np.nan
    ts = _ensure_utc_ts(ts)
    if ts in series.index:
        return float(series.loc[ts])
    # nearest within tolerance
    delta = (series.index - ts).total_seconds() / 60.0
    abs_delta = np.abs(delta)
    i = int(np.argmin(abs_delta))
    if abs_delta[i] <= tolerance_min:
        return float(series.iloc[i])
    return np.nan


def median_window_price(
    series: pd.Series,
    center: pd.Timestamp,
    window_min: int = 5,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> float:
    """Median of 1-min closes in ±window_min around center (or explicit [start, end])."""
    if series is None or series.empty:
        return np.nan
    if start is None or end is None:
        center = _ensure_utc_ts(center)
        start = center - pd.Timedelta(minutes=window_min)
        end = center + pd.Timedelta(minutes=window_min)
    else:
        start = _ensure_utc_ts(start)
        end = _ensure_utc_ts(end)
    win = series.loc[(series.index >= start) & (series.index <= end)].dropna()
    if win.empty:
        return np.nan
    return float(np.median(win.values))


def last_trade_age_min(volume: pd.Series, ts: pd.Timestamp) -> float:
    """Minutes since the last bar with volume > 0 at or before ts. NaN if none."""
    if volume is None or volume.empty:
        return np.nan
    ts = _ensure_utc_ts(ts)
    prior = volume.loc[volume.index <= ts]
    traded = prior[prior > 0]
    if traded.empty:
        return np.nan
    last = traded.index[-1]
    return float((ts - last).total_seconds() / 60.0)


def volume_at(volume: pd.Series, ts: pd.Timestamp, tolerance_min: int = 2) -> float:
    """Volume of the bar nearest to ts within tolerance."""
    if volume is None or volume.empty:
        return np.nan
    ts = _ensure_utc_ts(ts)
    if ts in volume.index:
        return float(volume.loc[ts])
    delta = (volume.index - ts).total_seconds() / 60.0
    abs_delta = np.abs(delta)
    i = int(np.argmin(abs_delta))
    if abs_delta[i] <= tolerance_min:
        return float(volume.iloc[i])
    return np.nan
