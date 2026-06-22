"""Governance schedule window helpers (weekdays + local time range)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Iterable, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from app.utils.governance_policy import EffectivePolicy

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_hhmm(value: str) -> Tuple[int, int]:
    match = _TIME_RE.match((value or "").strip())
    if not match:
        raise ValueError(f"invalid time '{value}', expected HH:MM")
    return int(match.group(1)), int(match.group(2))


def _minutes(hour: int, minute: int) -> int:
    return hour * 60 + minute


def is_time_in_range(
    *,
    current_minutes: int,
    start_minutes: int,
    end_minutes: int,
) -> bool:
    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes <= end_minutes
    # Overnight window (e.g. 22:00–06:00).
    return current_minutes >= start_minutes or current_minutes <= end_minutes


def is_governance_schedule_active(
    policy: "EffectivePolicy",
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Return True when scheduled governance jobs may run."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)

    weekdays = tuple(getattr(policy, "schedule_weekdays", ()) or ())
    if weekdays:
        try:
            tz = ZoneInfo(getattr(policy, "schedule_timezone", "UTC") or "UTC")
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("UTC")
        local = moment.astimezone(tz)
        if local.weekday() not in weekdays:
            return False
        start_h, start_m = parse_hhmm(getattr(policy, "schedule_start_time", "02:00"))
        end_h, end_m = parse_hhmm(getattr(policy, "schedule_end_time", "05:00"))
        return is_time_in_range(
            current_minutes=_minutes(local.hour, local.minute),
            start_minutes=_minutes(start_h, start_m),
            end_minutes=_minutes(end_h, end_m),
        )

    # Legacy fallback: explicit UTC hour list.
    hours = tuple(getattr(policy, "off_peak_hours_utc", ()) or ())
    return moment.astimezone(UTC).hour in hours


def normalize_weekdays(days: Iterable[int]) -> Tuple[int, ...]:
    unique = sorted({int(d) for d in days if 0 <= int(d) <= 6})
    if not unique:
        raise ValueError("schedule_weekdays must include at least one day")
    return tuple(unique)
