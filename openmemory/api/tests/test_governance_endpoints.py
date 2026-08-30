"""Tests for governance admin endpoints (task_11)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, Project
from app.routers import governance as governance_router


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(Project(name="proj-a"))
    db.commit()

    app = FastAPI()
    app.include_router(governance_router.router)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    yield TestClient(app)
    db.close()


ADMIN_HEADERS = {"x-admin-token": "test-admin-token"}


def test_put_invalid_policy_returns_400(client):
    resp = client.put(
        "/admin/governance/policies",
        json={"policy": {"similarity_threshold": 9}},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 400


def test_enqueue_job_returns_202(client, monkeypatch):
    class FakeQueue:
        def enqueue(self, job_type, project=None, payload=None, job_id=None):
            return "00000000-0000-0000-0000-000000000001"

    monkeypatch.setattr("app.routers.governance.governance_queue", FakeQueue())
    resp = client.post(
        "/admin/governance/jobs/dedup",
        json={"project": "proj-a"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_revert_non_quarantined_returns_409(client, monkeypatch):
    from app.routers import governance as gov_mod

    class FakeEngine:
        def revert(self, memory_id):
            return False

    monkeypatch.setattr(gov_mod, "QuarantineEngine", lambda: FakeEngine())
    resp = client.post(
        "/admin/governance/revert/00000000-0000-0000-0000-000000000099",
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 409


def test_quality_endpoint(client):
    resp = client.get("/admin/governance/quality")
    assert resp.status_code == 200
    assert "proxy_ratio" in resp.json()
def test_enqueue_disabled_process_returns_409(monkeypatch):
    from app.database import get_db
    from app.models import Base, Project
    from app.routers import governance as gov_router
    from app.utils.governance_policy import (
        DEFAULT_POLICY,
        default_processes_enabled,
        save_global_policy,
    )
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    db.add(Project(name="proj-a"))
    doc = {**DEFAULT_POLICY}
    disabled = default_processes_enabled()
    disabled["dedup"] = False
    doc["processes_enabled"] = disabled
    save_global_policy(db, doc)
    db.close()

    app = FastAPI()
    app.include_router(gov_router.router)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    # Desabilitado: 409 e nenhum job enfileirado.
    resp = client.post(
        "/admin/governance/jobs/dedup",
        json={"project": "proj-a"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 409
    assert "desabilitado" in resp.json()["detail"]

    # Reabilitado: 202.
    db = Session()
    doc2 = {**DEFAULT_POLICY}
    doc2["processes_enabled"] = default_processes_enabled()
    save_global_policy(db, doc2)
    db.close()

    class FakeQueue:
        def enqueue(self, job_type, project=None, payload=None, job_id=None):
            return "00000000-0000-0000-0000-000000000002"

    monkeypatch.setattr(gov_router, "governance_queue", FakeQueue())
    resp = client.post(
        "/admin/governance/jobs/dedup",
        json={"project": "proj-a"},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 202
    assert "job_id" in resp.json()
