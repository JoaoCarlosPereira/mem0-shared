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
