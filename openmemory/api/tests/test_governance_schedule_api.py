"""Tests for governance schedule API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import Base, Config
from app.routers.governance_schedule import router


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sched.db'}")
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def make_client(factory):
    app = FastAPI()
    app.include_router(router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def test_get_schedule_defaults(factory):
    client = make_client(factory)
    resp = client.get("/admin/governance/schedule")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schedule_timezone"] == "UTC"
    assert body["schedule_start_time"] == "02:00"
    assert 0 in body["schedule_weekdays"]


def test_put_schedule_persists(factory):
    client = make_client(factory)
    payload = {
        "schedule_timezone": "America/Sao_Paulo",
        "schedule_weekdays": [5, 6],
        "schedule_start_time": "01:30",
        "schedule_end_time": "04:45",
    }
    resp = client.put("/admin/governance/schedule", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["schedule_timezone"] == "America/Sao_Paulo"
    assert body["schedule_weekdays"] == [5, 6]

    db = factory()
    row = db.query(Config).filter(Config.key == "governance").one()
    db.close()
    assert row.value["schedule_start_time"] == "01:30"



# ---------------------------------------------------------------------------
# GET/PUT /admin/governance/processes
# ---------------------------------------------------------------------------


def test_get_processes_defaults(factory):
    client = make_client(factory)
    resp = client.get("/admin/governance/processes")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["processes_enabled"]) == {
        "dedup",
        "ttl_prune",
        "consolidate",
        "purge",
        "quality_eval",
        "enforce_quota",
        "cold_tier",
        "merge_projects",
    }
    assert body["processes_enabled"]["consolidate"] is False
    assert all(
        enabled
        for process, enabled in body["processes_enabled"].items()
        if process != "consolidate"
    )


def test_put_processes_requires_admin(factory, monkeypatch):
    client = make_client(factory)
    payload = {"processes_enabled": {"purge": False}}
    resp = client.put("/admin/governance/processes", json=payload)
    assert resp.status_code in (401, 403)

    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    headers = {"x-admin-token": "test-admin-token"}
    payload = {"processes_enabled": {k: True for k in (
        "dedup", "ttl_prune", "consolidate", "purge",
        "quality_eval", "enforce_quota", "cold_tier", "merge_projects",
    )}}
    payload["processes_enabled"]["purge"] = False
    resp = client.put(
        "/admin/governance/processes", json=payload, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["processes_enabled"]["purge"] is False

    db = factory()
    row = db.query(Config).filter(Config.key == "governance").one()
    db.close()
    assert row.value["processes_enabled"]["purge"] is False


def test_put_processes_rejects_unknown_or_missing_keys(factory, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")
    headers = {"x-admin-token": "test-admin-token"}
    client = make_client(factory)
    resp = client.put(
        "/admin/governance/processes",
        json={"processes_enabled": {"bogus": True}},
        headers=headers,
    )
    assert resp.status_code == 422
    resp = client.put(
        "/admin/governance/processes",
        json={"processes_enabled": {"purge": True}},
        headers=headers,
    )
    assert resp.status_code == 422
