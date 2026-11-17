"""Print and verify config holidays against CME Globex metals + LBMA gold calendars.

Sources (checked 2026-11-17):
- CME holiday hours: https://www.cmegroup.com/trading-hours.html
- CME 2025 summary (GC/metals): Good Friday full close; Mon holidays often early close/halt
- LBMA Gold Price calendars (ICE): https://www.ice.com/publicdocs/Gold_Holiday_Calendar_2025.pdf
  and 2026.pdf — UK bank holidays = no LBMA auction
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.calendar import is_holiday_weekend, list_fridays, latest_complete_friday


# Manual verification table: date → (name, CME metals note, LBMA note, keep_as_holiday_weekend?)
# keep=True means our Fri/Mon adjacency rule should flag the adjacent weekend.
CME_LBMA_NOTES: dict[str, dict[str, str]] = {
    "2025-01-01": {
        "name": "New Year's Day",
        "cme": "Metals closed (Wed) — does not create Fri/Mon 3-day gold weekend by itself",
        "lbma": "No auction (Wed)",
        "weekend_effect": "Wed holiday; Fri/Mon adjacency false unless listed Friday/Monday",
    },
    "2025-01-20": {
        "name": "MLK Day",
        "cme": "Metals early close / halt (Mon) — abbreviated Mon session, not full 3-day close",
        "lbma": "US holiday; LBMA usually auctions (UK open)",
        "weekend_effect": "Mon holiday → weekend Fri 2025-01-17 flagged",
    },
    "2025-02-17": {
        "name": "Presidents' Day",
        "cme": "Metals early close / halt (Mon)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Mon → weekend Fri 2025-02-14 flagged",
    },
    "2025-04-18": {
        "name": "Good Friday",
        "cme": "Metals FULLY CLOSED (Fri) — true 3-day gold weekend",
        "lbma": "No auction (Fri); Easter Monday 2025-04-21 also no auction",
        "weekend_effect": "Fri close → weekend Fri 2025-04-18 flagged (strongest case)",
    },
    "2025-05-26": {
        "name": "Memorial Day",
        "cme": "Metals early close / halt (Mon)",
        "lbma": "UK Spring Bank Holiday — no LBMA auction (Mon)",
        "weekend_effect": "Mon → weekend Fri 2025-05-23 flagged",
    },
    "2025-06-19": {
        "name": "Juneteenth",
        "cme": "Metals early close (Thu 2025) — mid-week, not Fri/Mon adjacency",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Thu — our Fri/Mon rule does NOT flag a weekend (correct)",
    },
    "2025-07-04": {
        "name": "Independence Day",
        "cme": "Metals early close (Fri)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Fri → weekend Fri 2025-07-04 flagged",
    },
    "2025-09-01": {
        "name": "Labor Day",
        "cme": "Metals early close / halt (Mon)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Mon → weekend Fri 2025-08-29 flagged",
    },
    "2025-11-27": {
        "name": "Thanksgiving",
        "cme": "Metals early close / halt (Thu) — mid-week",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Thu — Fri/Mon rule does NOT flag (correct); day-after may early-close Fri",
    },
    "2025-12-25": {
        "name": "Christmas",
        "cme": "Metals CLOSED (Thu)",
        "lbma": "No auction Christmas + Boxing Day (Thu–Fri)",
        "weekend_effect": "Thu/Fri cluster — Fri 2025-12-26 is Boxing Day (LBMA); consider adding 2025-12-26",
    },
    "2026-01-01": {
        "name": "New Year's Day",
        "cme": "Metals closed (Thu)",
        "lbma": "No auction (Thu)",
        "weekend_effect": "Thu — not Fri/Mon adjacency",
    },
    "2026-01-19": {
        "name": "MLK Day",
        "cme": "Metals halt ~2:30 p.m. CT, reopen 6 p.m. (Mon)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Mon → weekend Fri 2026-01-16 flagged",
    },
    "2026-02-16": {
        "name": "Presidents' Day",
        "cme": "Metals halt (Mon)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Mon → weekend Fri 2026-02-13 flagged",
    },
    "2026-04-03": {
        "name": "Good Friday",
        "cme": "Metals FULLY CLOSED (Fri) — true 3-day gold weekend",
        "lbma": "No auction (Fri); Easter Monday 2026-04-06 also no auction",
        "weekend_effect": "Fri → weekend Fri 2026-04-03 flagged (strongest case)",
    },
    "2026-05-25": {
        "name": "Memorial Day / UK Spring Bank",
        "cme": "Metals halt (Mon)",
        "lbma": "No auction (Mon)",
        "weekend_effect": "Mon → weekend Fri 2026-05-22 flagged",
    },
    "2026-06-19": {
        "name": "Juneteenth",
        "cme": "Metals early close (Fri)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Fri → weekend Fri 2026-06-19 flagged",
    },
    "2026-07-03": {
        "name": "Independence Day observed",
        "cme": "Metals early close (Fri)",
        "lbma": "US holiday observed; LBMA usually auctions",
        "weekend_effect": "Fri → weekend Fri 2026-07-03 flagged",
    },
    "2026-09-07": {
        "name": "Labor Day",
        "cme": "Metals halt (Mon)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Mon → weekend Fri 2026-09-04 flagged",
    },
    "2026-11-26": {
        "name": "Thanksgiving",
        "cme": "Metals halt (Thu)",
        "lbma": "US holiday; LBMA usually auctions",
        "weekend_effect": "Thu — Fri/Mon rule does NOT flag",
    },
    "2026-12-25": {
        "name": "Christmas",
        "cme": "Metals CLOSED (Fri) — true long weekend",
        "lbma": "No auction Christmas (Fri) + Boxing Day observed Mon 2026-12-28",
        "weekend_effect": "Fri → weekend Fri 2026-12-25 flagged; also Mon 12-28 LBMA closed",
    },
}


def verify_holidays(cfg: dict[str, Any]) -> str:
    """Return markdown report of holiday list vs CME/LBMA notes + flagged weekends."""
    holidays = [str(h) for h in cfg.get("holidays", [])]
    start = date.fromisoformat(str(cfg["sample_start"]))
    end = latest_complete_friday()
    fridays = list_fridays(start, end)
    flagged = [f for f in fridays if is_holiday_weekend(f, holidays)]

    lines = [
        "Config `holidays` dates and CME metals / LBMA notes:",
        "",
        "| Date | Name | CME metals | LBMA | Our Fri/Mon flag effect |",
        "|------|------|------------|------|-------------------------|",
    ]
    for h in holidays:
        note = CME_LBMA_NOTES.get(h, {})
        lines.append(
            f"| {h} | {note.get('name', '?')} | {note.get('cme', 'verify manually')} | "
            f"{note.get('lbma', 'verify manually')} | {note.get('weekend_effect', '')} |"
        )

    lines += [
        "",
        f"**Weekends flagged `holiday_weekend=True` in sample ({start} → {end}):** "
        + (", ".join(f.isoformat() for f in flagged) if flagged else "(none)"),
        "",
        "**Verification notes (v2.1):**",
        "- True full gold closes that match the study’s 3-day-weekend intent: "
        "**Good Friday** (2025-04-18, 2026-04-03) and **Christmas 2026-12-25** (Fri).",
        "- Many US Mon holidays are CME metals *early close / midday halt*, not a full Friday–Monday "
        "gold blackout; Dukascopy may still have quotes. We still exclude them as configured "
        "(conservative) and report holiday-only Q2/Q3 separately.",
        "- Mid-week holidays (NYD Wed/Thu, Thanksgiving Thu, Juneteenth 2025 Thu) do **not** "
        "trip Fri/Mon adjacency — expected.",
        "- Optional adds (not required for v2.1): LBMA **Easter Monday** (2025-04-21, 2026-04-06), "
        "**Boxing Day 2025-12-26**, **Boxing Day observed 2026-12-28**, UK Early May / Summer Bank.",
        "- Sources: CME trading-hours holiday schedule; ICE LBMA Gold Holiday Calendar 2025/2026 PDFs.",
    ]
    return "\n".join(lines)


def print_holiday_list(cfg: dict[str, Any]) -> str:
    text = verify_holidays(cfg)
    print(text)
    return text
