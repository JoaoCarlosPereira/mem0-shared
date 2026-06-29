"""Tests for project delete (Qdrant + SQL catalog)."""

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
from app.models import Base, Project
from app.routers.apps import router as apps_router
from app.utils.project_apps import project_to_app_id


@pytest.fixture(autouse=True)
def _clear_delete_flags(monkeypatch):
    monkeypatch.delenv("MEM0_ALLOW_MEMORY_DELETE", raising=False)
    monkeypatch.delenv("MEM0_ALLOW_BULK_DELETE", raising=False)


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield factory
    engine.dispose()


def _client(factory):
    app = FastAPI()
    app.include_router(apps_router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


class TestProjectDelete:
    def test_delete_project_blocked_by_default(self, db_factory):
        db = db_factory()
        db.add(Project(name="demo"))
        db.commit()
        db.close()

        app_id = project_to_app_id("demo")
        client = _client(db_factory)
        resp = client.post(
            f"/api/v1/apps/{app_id}/actions/delete",
            json={"confirm_name": "demo", "user_id": "openmemory"},
        )
        assert resp.status_code == 403

    def test_delete_project_requires_name_confirmation(self, db_factory, monkeypatch):
        monkeypatch.setenv("MEM0_ALLOW_MEMORY_DELETE", "1")
        monkeypatch.setenv("MEM0_ALLOW_BULK_DELETE", "1")

        db = db_factory()
        db.add(Project(name="demo"))
        db.commit()
        db.close()

        app_id = project_to_app_id("demo")
        client = _client(db_factory)
        resp = client.post(
            f"/api/v1/apps/{app_id}/actions/delete",
            json={"confirm_name": "wrong", "user_id": "openmemory"},
        )
        assert resp.status_code == 400

    def test_delete_project_removes_qdrant_points(self, db_factory, monkeypatch):
        monkeypatch.setenv("MEM0_ALLOW_MEMORY_DELETE", "1")
        monkeypatch.setenv("MEM0_ALLOW_BULK_DELETE", "1")

        db = db_factory()
        db.add(Project(name="demo"))
        db.commit()
        db.close()

        app_id = project_to_app_id("demo")
        mock_client = MagicMock()
        client = _client(db_factory)

        with patch(
            "app.utils.project_delete.get_memory_client_safe",
            return_value=mock_client,
        ), patch(
            "app.utils.project_delete.bind_active_collection",
        ), patch(
            "app.utils.project_delete.read_cache.invalidate_search",
        ) as invalidate:
            mock_vs = mock_client.vector_store
            point = MagicMock()
            point.id = uuid.uuid4()
            mock_vs._create_filter.return_value = "filter"
            mock_vs.collection_name = "openmemory"
            mock_vs.client.scroll.side_effect = [([point], None)]

            resp = client.post(
                f"/api/v1/apps/{app_id}/actions/delete",
                json={"confirm_name": "demo", "user_id": "openmemory"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted_memories"] == 1
        assert body["project"] == "demo"
        mock_client.delete.assert_called_once_with(str(point.id))
        invalidate.assert_called_once_with("demo")

        db = db_factory()
        assert db.query(Project).filter(Project.name == "demo").first() is None
        db.close()
