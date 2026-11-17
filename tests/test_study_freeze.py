"""study_end_date must exclude later weekends from the study sample flag."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.calendar import build_weekend_index


def test_study_end_date_flags_oos_but_keeps_rows():
    cfg = {
        "sample_start": "2025-01-01",
        "study_end_date": "2025-02-07",
        "friday_close_et": "17:00",
        "sunday_reopen_et": "18:00",
        "pre_open_offset_min": 5,
        "regime_split_date": "2026-01-01",
        "holidays": [],
    }
    # Pretend "now" is late 2025 so latest_complete is after the freeze
    now = datetime(2025, 6, 15, tzinfo=ZoneInfo("UTC"))
    idx = build_weekend_index(cfg, now_utc=now)
    assert idx["friday_date"].max() > date(2025, 2, 7)
    in_sample = idx.loc[idx["study_sample"]]
    oos = idx.loc[~idx["study_sample"]]
    assert in_sample["friday_date"].max() == date(2025, 2, 7)
    assert len(oos) > 0
    assert oos["friday_date"].min() > date(2025, 2, 7)
