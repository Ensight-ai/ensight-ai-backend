"""Turn busy intervals into a few suggestable open meeting slots.

Pure logic (no I/O) so it's easy to reason about and test: given the calendar's
busy blocks and a working-hours policy, produce the next handful of free start
times in the owner's timezone.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# Don't offer slots starting sooner than this from now.
_MIN_LEAD = timedelta(hours=1)


def _overlaps(
    start: datetime, end: datetime, busy: list[tuple[datetime, datetime]]
) -> bool:
    return any(start < b_end and b_start < end for b_start, b_end in busy)


def compute_free_slots(
    busy: list[tuple[datetime, datetime]],
    *,
    now: datetime,
    timezone: str,
    duration_minutes: int,
    workday_start_hour: int,
    workday_end_hour: int,
    lookahead_business_days: int,
    max_slots: int = 5,
) -> list[datetime]:
    """Return up to ``max_slots`` free start times (tz-aware, owner's tz).

    Walks forward business day by business day (Mon–Fri), stepping through the
    working-hours window in ``duration_minutes`` increments and keeping slots
    that are in the future and don't overlap a busy block.
    """
    tz = ZoneInfo(timezone)
    duration = timedelta(minutes=duration_minutes)
    earliest = now.astimezone(tz) + _MIN_LEAD

    slots: list[datetime] = []
    business_days_seen = 0
    day_offset = 0
    today = now.astimezone(tz).date()

    while business_days_seen < lookahead_business_days and len(slots) < max_slots:
        current = today + timedelta(days=day_offset)
        day_offset += 1
        if current.weekday() >= 5:  # Sat/Sun
            continue
        business_days_seen += 1

        slot = datetime.combine(current, time(workday_start_hour), tzinfo=tz)
        day_end = datetime.combine(current, time(workday_end_hour), tzinfo=tz)
        while slot + duration <= day_end and len(slots) < max_slots:
            if slot >= earliest and not _overlaps(slot, slot + duration, busy):
                slots.append(slot)
            slot += duration

    return slots
