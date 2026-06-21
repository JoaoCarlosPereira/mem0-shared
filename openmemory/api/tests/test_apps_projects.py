"""Regression tests for Apps tab listing MCP projects from Qdrant."""

import os
import uuid
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import App, Base, Project, User
from app.routers.apps import router as apps_router
from app.utils.project_apps import project_to_app_id


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


def _apps_client(factory):
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


def _seed_projects_and_sql_app(factory):
    db = factory()
    user = User(user_id="root", name="Root")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(App(name="openmemory", owner_id=user.id, is_active=True))
    db.add(Project(name="sysmovs"))
    db.add(Project(name="default"))
    db.commit()
    db.close()


class TestAppsProjectListing:
    def test_list_apps_includes_projects_with_qdrant_counts(self, db_factory):
        _seed_projects_and_sql_app(db_factory)

        def _count(project: str) -> int:
            return {"sysmovs": 288, "default": 29}.get(project, 0)

        client = _apps_client(db_factory)
        with patch("app.routers.apps.count_project_memories", side_effect=_count):
            resp = client.get("/api/v1/apps/", params={"page": 1, "page_size": 20})

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        names = {app["name"] for app in body["apps"]}
        assert names == {"openmemory", "sysmovs", "default"}

        by_name = {app["name"]: app for app in body["apps"]}
        assert by_name["sysmovs"]["total_memories_created"] == 288
        assert by_name["default"]["total_memories_created"] == 29

    def test_get_project_app_details(self, db_factory):
        _seed_projects_and_sql_app(db_factory)
        app_id = project_to_app_id("sysmovs")
        client = _apps_client(db_factory)

        with patch("app.routers.apps.count_project_memories", return_value=288):
            resp = client.get(f"/api/v1/apps/{app_id}")

        assert resp.status_code == 200
        assert resp.json()["total_memories_created"] == 288

    def test_list_project_app_memories_from_qdrant(self, db_factory):
        _seed_projects_and_sql_app(db_factory)
        app_id = project_to_app_id("sysmovs")
        client = _apps_client(db_factory)
        payload = {
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "content": "project memory",
                    "created_at": "2026-06-21T00:00:00+00:00",
                    "state": "active",
                    "app_name": "sysmovs",
                    "categories": [],
                    "metadata_": {},
                }
            ],
            "total": 1,
            "page": 1,
            "size": 10,
            "pages": 1,
        }

        with patch("app.routers.apps.list_shared_memories", return_value=payload) as mock_list:
            resp = client.get(f"/api/v1/apps/{app_id}/memories", params={"page": 1, "page_size": 10})

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["memories"][0]["content"] == "project memory"
        mock_list.assert_called_once_with(project="sysmovs", page=1, size=10)

    def test_project_accessed_memories_empty(self, db_factory):
        _seed_projects_and_sql_app(db_factory)
        app_id = project_to_app_id("sysmovs")
        client = _apps_client(db_factory)
        resp = client.get(f"/api/v1/apps/{app_id}/accessed")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
