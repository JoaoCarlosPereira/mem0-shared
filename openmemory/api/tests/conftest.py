"""Shared pytest hooks for OpenMemory API tests."""

import datetime

import pytest

# ``datetime.UTC`` exists only on Python 3.11+; CI still runs 3.10.
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _isolate_production_dotenv(monkeypatch):
    """Keep unit tests independent of a developer/production ``api/.env``."""
    monkeypatch.delenv("OPENMEMORY_DISCOVERY_BASE_URL", raising=False)
