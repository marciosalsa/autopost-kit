"""Date helpers that are timezone-aware, so "tomorrow" means the same day everywhere."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def target_date(timezone: str, days_ahead: int = 1, now: datetime | None = None) -> date:
    """Return the calendar day ``days_ahead`` days from now in ``timezone``.

    ``now`` can be injected for tests; it must be timezone-aware.
    """
    tz = ZoneInfo(timezone)
    current = now.astimezone(tz) if now else datetime.now(tz)
    return current.date() + timedelta(days=days_ahead)
