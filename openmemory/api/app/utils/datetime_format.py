"""Serialização de datetimes UTC para JSON/API."""

import datetime


def format_utc_iso(dt: datetime.datetime | None) -> str:
    """Serialize a UTC datetime with explicit ``Z`` suffix for clients."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        return f"{dt.isoformat()}Z"
    return dt.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
