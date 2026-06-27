"""Tests for fail-closed memory deletion guard."""

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.database import get_db
from app.models import Base
from app.routers.memories import router as memories_router
from app.utils.deletion_guard import (
    DeletionBlockedError,
    assert_bulk_delete_allowed,
    assert_memory_delete_allowed,
    bulk_delete_allowed,
    memory_delete_allowed,
)


@pytest.fixture(autouse=True)
def _clear_delete_flags(monkeypatch):
    monkeypatch.delenv("MEM0_ALLOW_MEMORY_DELETE", raising=False)
    monkeypatch.delenv("MEM0_ALLOW_BULK_DELETE", raising=False)


def test_delete_blocked_by_default():
    assert memory_delete_allowed() is False
    assert bulk_delete_allowed() is False
    with pytest.raises(DeletionBlockedError):
        assert_memory_delete_allowed("delete")
    with pytest.raises(DeletionBlockedError):
        assert_bulk_delete_allowed("delete_all")


def test_delete_allowed_when_env_set(monkeypatch):
    monkeypatch.setenv("MEM0_ALLOW_MEMORY_DELETE", "1")
    monkeypatch.setenv("MEM0_ALLOW_BULK_DELETE", "1")
    assert memory_delete_allowed() is True
    assert bulk_delete_allowed() is True
    assert_memory_delete_allowed("delete")
    assert_bulk_delete_allowed("delete_all")


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _client(db_factory):
    app = FastAPI()
    app.include_router(memories_router)

    def _override():
        s = db_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def test_api_delete_returns_403_when_guard_active(db_factory):
    mem_id = uuid.uuid4()
    client = _client(db_factory)

    resp = client.post(
        "/api/v1/memories/actions/delete",
        json={"memory_ids": [str(mem_id)], "user_id": "openmemory"},
    )

    assert resp.status_code == 403
    assert "blocked" in resp.json()["detail"].lower()


def test_api_delete_succeeds_when_guard_disabled(db_factory, monkeypatch):
    monkeypatch.setenv("MEM0_ALLOW_MEMORY_DELETE", "1")
    mem_id = uuid.uuid4()
    mock_client = MagicMock()
    client = _client(db_factory)

    with patch("app.utils.memory.get_memory_client_safe", return_value=mock_client):
        resp = client.post(
            "/api/v1/memories/actions/delete",
            json={"memory_ids": [str(mem_id)], "user_id": "openmemory"},
        )

    assert resp.status_code == 200
    mock_client.delete.assert_called_once_with(str(mem_id))
