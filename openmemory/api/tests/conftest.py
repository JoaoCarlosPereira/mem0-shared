"""Shared pytest hooks for OpenMemory API tests."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_production_dotenv(monkeypatch):
    """Keep unit tests independent of a developer/production ``api/.env``."""
    monkeypatch.delenv("OPENMEMORY_DISCOVERY_BASE_URL", raising=False)
