"""Shared UTC datetime helpers for naive-DB vs aware-clock arithmetic."""

from __future__ import annotations

from datetime import datetime, timezone


def as_utc_naive(dt: datetime) -> datetime:
    """Normalize DB (naive UTC) and aware UTC clocks for comparisons."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def utc_now_naive() -> datetime:
    """Current UTC as naive datetime (matches SQLAlchemy DateTime columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
