"""Regression tests for shared MCP/Qdrant memory listing and SQL filter fixes.

Covers:
- POST /api/v1/memories/shared-filter (dashboard reads Qdrant, not empty SQL)
- POST /api/v1/memories/filter DISTINCT ON ordering (PostgreSQL compatibility)
- GET /api/v1/stats/ uses Qdrant totals when SQL catalog is empty
"""

import os
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import App, Base, Memory, MemoryState, User
from app.routers.memories import router as memories_router
from app.routers.stats import router as stats_router


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


def _seed_user_with_memories(factory):
    db = factory()
    user = User(user_id="root", name="Root")
    db.add(user)
    db.commit()
    db.refresh(user)
    app = App(name="openmemory", owner_id=user.id)
    db.add(app)
    db.commit()
    db.refresh(app)
    for i in range(3):
        db.add(
            Memory(
                user_id=user.id,
                app_id=app.id,
                content=f"memory-{i}",
                state=MemoryState.active,
                created_at=datetime.now(UTC),
            )
        )
    db.commit()
    db.close()
    return user


def _memories_client(factory):
    app = FastAPI()
    app.include_router(memories_router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _stats_client(factory):
    app = FastAPI()
    app.include_router(stats_router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


class TestSharedFilterEndpoint:
    def test_shared_filter_returns_qdrant_memories(self, db_factory):
        payload = {
            "items": [
                {
                    "id": str(uuid.uuid4()),
                    "content": "shared fact",
                    "created_at": "2026-06-21T00:00:00+00:00",
                    "state": "active",
                    "app_id": None,
                    "app_name": "sysmovs",
                    "created_by_hostname": "S0293",
                    "categories": [],
                    "metadata_": {"project": "sysmovs", "hostname": "S0293"},
                }
            ],
            "total": 1,
            "page": 1,
            "size": 10,
            "pages": 1,
        }
        client = _memories_client(db_factory)
        with (
            patch(
                "app.utils.vector_stats.list_shared_memories",
                return_value=payload,
            ) as mock_list,
            patch(
                "app.routers.memories.group_name_for_hostname",
                return_value="Default",
            ),
        ):
            resp = client.post(
                "/api/v1/memories/shared-filter",
                json={"user_id": "root", "page": 1, "size": 10},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["content"] == "shared fact"
        assert body["items"][0]["app_name"] == "sysmovs"
        assert body["items"][0]["group"] == "Default"
        mock_list.assert_called_once()

    def test_shared_filter_source_routes_through_filter(self, db_factory):
        client = _memories_client(db_factory)
        with patch(
            "app.utils.vector_stats.list_shared_memories",
            return_value={
                "items": [],
                "total": 0,
                "page": 1,
                "size": 10,
                "pages": 0,
            },
        ):
            resp = client.post(
                "/api/v1/memories/filter",
                json={"user_id": "root", "page": 1, "size": 10, "source": "shared"},
            )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestSqlFilterDistinctOnRegression:
    def test_filter_sql_path_does_not_500_with_categories_join(self, db_factory):
        _seed_user_with_memories(db_factory)
        client = _memories_client(db_factory)
        resp = client.post(
            "/api/v1/memories/filter",
            json={"user_id": "root", "page": 1, "size": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    def test_filter_sql_path_supports_sort_without_error(self, db_factory):
        _seed_user_with_memories(db_factory)
        client = _memories_client(db_factory)
        resp = client.post(
            "/api/v1/memories/filter",
            json={
                "user_id": "root",
                "page": 1,
                "size": 10,
                "sort_column": "created_at",
                "sort_direction": "desc",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3


class TestStatsRegression:
    def test_stats_uses_qdrant_total_when_sql_empty(self, db_factory):
        db = db_factory()
        db.add(User(user_id="root", name="Root"))
        db.commit()
        db.close()

        client = _stats_client(db_factory)
        with patch("app.routers.stats.count_collection_memories", return_value=525):
            resp = client.get("/api/v1/stats/", params={"user_id": "root"})

        assert resp.status_code == 200
        assert resp.json()["total_memories"] == 525

    def test_stats_returns_404_for_unknown_user(self, db_factory):
        client = _stats_client(db_factory)
        resp = client.get("/api/v1/stats/", params={"user_id": "missing"})
        assert resp.status_code == 404


class TestGetMemoryQdrantFallback:
    def test_get_memory_returns_qdrant_memory_when_not_in_sql(self, db_factory):
        mem_id = str(uuid.uuid4())
        qdrant_payload = {
            "id": mem_id,
            "text": "from qdrant",
            "created_at": 1718951717,
            "state": "active",
            "app_id": None,
            "app_name": "sysmovs",
            "categories": [],
            "metadata_": {"project": "sysmovs", "data": "from qdrant"},
        }
        client = _memories_client(db_factory)
        with patch(
            "app.utils.vector_stats.get_shared_memory_by_id",
            return_value=qdrant_payload,
        ) as mock_get:
            resp = client.get(f"/api/v1/memories/{mem_id}", params={"user_id": "root"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["text"] == "from qdrant"
        assert body["app_name"] == "sysmovs"
        mock_get.assert_called_once_with(mem_id)

    def test_get_memory_404_when_missing_everywhere(self, db_factory):
        mem_id = str(uuid.uuid4())
        client = _memories_client(db_factory)
        with patch("app.utils.vector_stats.get_shared_memory_by_id", return_value=None):
            resp = client.get(f"/api/v1/memories/{mem_id}", params={"user_id": "root"})
        assert resp.status_code == 404

    def test_related_memories_empty_for_qdrant_only_memory(self, db_factory):
        mem_id = str(uuid.uuid4())
        db = db_factory()
        db.add(User(user_id="root", name="Root"))
        db.commit()
        db.close()

        client = _memories_client(db_factory)
        with patch("app.utils.vector_stats.get_shared_memory_by_id", return_value={"id": mem_id}):
            resp = client.get(
                f"/api/v1/memories/{mem_id}/related",
                params={"user_id": "root"},
            )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
