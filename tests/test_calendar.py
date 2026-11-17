"""Weekend calendar: DST, holidays, reopen UTC offsets."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.calendar import (
    friday_close_utc,
    is_holiday_weekend,
    list_fridays,
    saturday_noon_utc,
    sunday_reopen_utc,
)

CFG = {
    "friday_close_et": "17:00",
    "sunday_reopen_et": "18:00",
    "pre_open_offset_min": 5,
}


def test_winter_reopen_is_2300_utc():
    # 2025-01-10 is a Friday in US winter (EST = UTC−5)
    fri = date(2025, 1, 10)
    reopen = sunday_reopen_utc(fri, CFG)
    assert reopen.astimezone(ZoneInfo("UTC")).hour == 23
    assert reopen.astimezone(ZoneInfo("UTC")).minute == 0
    assert reopen.date().isoformat() == "2025-01-12"


def test_summer_reopen_is_2200_utc():
    # 2025-07-11 is a Friday in US summer (EDT = UTC−4)
    fri = date(2025, 7, 11)
    reopen = sunday_reopen_utc(fri, CFG)
    assert reopen.astimezone(ZoneInfo("UTC")).hour == 22
    assert reopen.date().isoformat() == "2025-07-13"


def test_friday_close_winter():
    fri = date(2025, 1, 10)
    close = friday_close_utc(fri, CFG)
    # 17:00 EST = 22:00 UTC
    assert close.astimezone(ZoneInfo("UTC")).hour == 22


def test_friday_close_summer():
    fri = date(2025, 7, 11)
    close = friday_close_utc(fri, CFG)
    # 17:00 EDT = 21:00 UTC
    assert close.astimezone(ZoneInfo("UTC")).hour == 21


def test_holiday_weekend_good_friday():
    # Good Friday 2025-04-18 → that Friday is a holiday weekend
    assert is_holiday_weekend(date(2025, 4, 18), ["2025-04-18"])
    assert not is_holiday_weekend(date(2025, 4, 11), ["2025-04-18"])


def test_holiday_on_monday_flags_prior_friday():
    # Memorial Day 2025-05-26 Monday → Friday 2025-05-23 is holiday weekend
    assert is_holiday_weekend(date(2025, 5, 23), ["2025-05-26"])


def test_list_fridays_aligns():
    fridays = list_fridays(date(2025, 1, 1), date(2025, 1, 31))
    assert fridays[0] == date(2025, 1, 3)
    assert all(f.weekday() == 4 for f in fridays)


def test_saturday_noon_placebo():
    fri = date(2025, 1, 10)
    noon = saturday_noon_utc(fri)
    assert noon.astimezone(ZoneInfo("America/New_York")).hour == 12
    assert noon.astimezone(ZoneInfo("America/New_York")).date().isoformat() == "2025-01-11"
