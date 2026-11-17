"""Weekend calendar: Friday close, Sunday reopen, DST, holidays.

All ET wall-clock times use America/New_York so DST is handled by zoneinfo.
Sunday 18:00 ET = 23:00 UTC in US winter (EST) and 22:00 UTC in US summer (EDT).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def parse_hhmm(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def et_to_utc(dt_et: datetime) -> datetime:
    """Convert an America/New_York datetime to UTC (aware)."""
    if dt_et.tzinfo is None:
        dt_et = dt_et.replace(tzinfo=ET)
    return dt_et.astimezone(UTC)


def friday_close_utc(friday: date, cfg: dict[str, Any]) -> datetime:
    """Friday gold close timestamp in UTC."""
    t = parse_hhmm(cfg.get("friday_close_et", "17:00"))
    return et_to_utc(datetime.combine(friday, t, tzinfo=ET))


def sunday_reopen_utc(friday: date, cfg: dict[str, Any]) -> datetime:
    """Sunday gold reopen (Fri + 2 days at 18:00 ET) in UTC."""
    sunday = friday + timedelta(days=2)
    t = parse_hhmm(cfg.get("sunday_reopen_et", "18:00"))
    return et_to_utc(datetime.combine(sunday, t, tzinfo=ET))


def pre_open_utc(friday: date, cfg: dict[str, Any]) -> datetime:
    """Token decision time: reopen − pre_open_offset_min."""
    reopen = sunday_reopen_utc(friday, cfg)
    return reopen - timedelta(minutes=int(cfg.get("pre_open_offset_min", 5)))


def post_open_utc(friday: date, cfg: dict[str, Any], minutes: int = 0, hours: int = 0) -> datetime:
    """Timestamp minutes/hours after Sunday reopen."""
    return sunday_reopen_utc(friday, cfg) + timedelta(minutes=minutes, hours=hours)


def saturday_noon_utc(friday: date) -> datetime:
    """Placebo 'reopen' at Saturday 12:00 ET."""
    saturday = friday + timedelta(days=1)
    return et_to_utc(datetime.combine(saturday, time(12, 0), tzinfo=ET))


def list_fridays(sample_start: date, sample_end: date) -> list[date]:
    """All Fridays with Friday in [sample_start, sample_end] inclusive."""
    # Align to first Friday on/after sample_start
    d = sample_start
    while d.weekday() != 4:  # Monday=0 … Friday=4
        d += timedelta(days=1)
    out: list[date] = []
    while d <= sample_end:
        out.append(d)
        d += timedelta(days=7)
    return out


def is_holiday_weekend(friday: date, holidays: list[str] | list[date]) -> bool:
    """True if a configured holiday falls on Fri/Mon adjacent to this weekend.

    Gold 3-day weekends: holiday on Friday (early close week) or Monday
    after the Sunday reopen.
    """
    holiday_dates = {
        date.fromisoformat(h) if isinstance(h, str) else h for h in holidays
    }
    monday = friday + timedelta(days=3)
    return friday in holiday_dates or monday in holiday_dates


def latest_complete_friday(now_utc: datetime | None = None) -> date:
    """Most recent Friday whose Sunday reopen + 4h has already passed."""
    now = now_utc or datetime.now(tz=UTC)
    # Candidate: most recent Friday on/before today in ET
    now_et = now.astimezone(ET)
    d = now_et.date()
    while d.weekday() != 4:
        d -= timedelta(days=1)
    # Need reopen + 4h completed
    cfg_min = {"friday_close_et": "17:00", "sunday_reopen_et": "18:00", "pre_open_offset_min": 5}
    cutoff = post_open_utc(d, cfg_min, hours=4)
    if now < cutoff:
        d -= timedelta(days=7)
    return d


def weekend_id(friday: date) -> str:
    return friday.isoformat()


def build_weekend_index(cfg: dict[str, Any], now_utc: datetime | None = None) -> pd.DataFrame:
    """Table of weekends from sample_start through the latest complete weekend.

    When study_end_date is set, later weekends remain in the panel with
    study_sample=False so a strategy phase can use them as clean OOS data.
    """
    start = date.fromisoformat(str(cfg["sample_start"]))
    end_cap = cfg.get("study_end_date")
    end = latest_complete_friday(now_utc)
    freeze = date.fromisoformat(str(end_cap)) if end_cap else None
    holidays = cfg.get("holidays", [])
    rows = []
    for fri in list_fridays(start, end):
        reopen = sunday_reopen_utc(fri, cfg)
        rows.append(
            {
                "weekend_id": weekend_id(fri),
                "friday_date": fri,
                "friday_close_utc": friday_close_utc(fri, cfg),
                "pre_open_utc": pre_open_utc(fri, cfg),
                "reopen_utc": reopen,
                "holiday_weekend": is_holiday_weekend(fri, holidays),
                "regime": "pre_2026"
                if fri < date.fromisoformat(str(cfg["regime_split_date"]))
                else "post_2026",
                "study_sample": True if freeze is None else fri <= freeze,
            }
        )
    return pd.DataFrame(rows)
