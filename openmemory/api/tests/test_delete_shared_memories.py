"""Regression: delete must work for Qdrant-only memories (shared-filter UI path)."""

import os
import uuid
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base
from app.routers.memories import router as memories_router


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


class TestDeleteSharedMemories:
    def test_post_actions_delete_qdrant_only_memory(self, db_factory):
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
        assert "Successfully deleted" in resp.json()["message"]

    def test_post_actions_delete_creates_user_when_missing(self, db_factory):
        mem_id = uuid.uuid4()
        mock_client = MagicMock()
        client = _client(db_factory)

        with patch("app.utils.memory.get_memory_client_safe", return_value=mock_client):
            resp = client.post(
                "/api/v1/memories/actions/delete",
                json={"memory_ids": [str(mem_id)], "user_id": "new-ui-user"},
            )

        assert resp.status_code == 200

    def test_post_actions_delete_404_when_nothing_removed(self, db_factory):
        mem_id = uuid.uuid4()
        mock_client = MagicMock()
        mock_client.delete.side_effect = RuntimeError("not found")
        client = _client(db_factory)

        with patch("app.utils.memory.get_memory_client_safe", return_value=mock_client):
            resp = client.post(
                "/api/v1/memories/actions/delete",
                json={"memory_ids": [str(mem_id)], "user_id": "openmemory"},
            )

        assert resp.status_code == 404
