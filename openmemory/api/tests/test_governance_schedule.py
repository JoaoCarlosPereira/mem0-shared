"""Tests for governance schedule window."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.utils.governance_policy import EffectivePolicy
from app.utils.governance_schedule import (
    is_governance_schedule_active,
    is_time_in_range,
    normalize_weekdays,
    parse_hhmm,
)


def _policy(**kwargs) -> EffectivePolicy:
    base = dict(
        ttl_max_age_days=365,
        ttl_idle_days=90,
        quarantine_window_days=30,
        consolidation_enabled=False,
        similarity_threshold=0.92,
        contradiction_tiebreak="recency",
        schedule_timezone="America/Sao_Paulo",
        schedule_weekdays=(5, 6),
        schedule_start_time="02:00",
        schedule_end_time="05:30",
        off_peak_hours_utc=(2, 3, 4, 5),
    )
    base.update(kwargs)
    return EffectivePolicy(**base)


def test_parse_hhmm_valid():
    assert parse_hhmm("02:30") == (2, 30)


def test_parse_hhmm_invalid():
    with pytest.raises(ValueError):
        parse_hhmm("25:00")


def test_normalize_weekdays_dedupes_and_sorts():
    assert normalize_weekdays([6, 0, 0, 6]) == (0, 6)


def test_schedule_active_on_configured_weekend_window():
    # Saturday 03:15 in São Paulo (UTC-3) => 06:15 UTC
    moment = datetime(2026, 6, 20, 6, 15, tzinfo=UTC)
    assert is_governance_schedule_active(_policy(), now=moment) is True


def test_schedule_inactive_on_weekday():
    # Friday 03:00 São Paulo => 06:00 UTC
    moment = datetime(2026, 6, 19, 6, 0, tzinfo=UTC)
    assert is_governance_schedule_active(_policy(), now=moment) is False


def test_schedule_inactive_outside_hours():
    moment = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)  # Sunday noon UTC
    assert is_governance_schedule_active(_policy(), now=moment) is False


def test_legacy_off_peak_hours_fallback():
    policy = _policy(schedule_weekdays=())
    moment = datetime(2026, 6, 19, 3, 0, tzinfo=UTC)
    assert is_governance_schedule_active(policy, now=moment) is True
    moment = datetime(2026, 6, 19, 10, 0, tzinfo=UTC)
    assert is_governance_schedule_active(policy, now=moment) is False


def test_overnight_window():
    assert is_time_in_range(current_minutes=23 * 60, start_minutes=22 * 60, end_minutes=2 * 60)
    assert not is_time_in_range(current_minutes=12 * 60, start_minutes=22 * 60, end_minutes=2 * 60)
