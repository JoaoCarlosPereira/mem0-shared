"""Tests for POST /admin/write-queue/retry-failed."""

import importlib.util
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, WriteQueueJob, WriteQueueStatus

_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "routers" / "admin_write_queue.py"
)
_spec = importlib.util.spec_from_file_location("admin_write_queue_under_test", _PATH)
_router_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_router_mod)
router = _router_mod.router


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
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


def _failed_job(project="proj-a", text="hello", attempts=3):
    return WriteQueueJob(
        project=project,
        hostname="host1",
        client_name="cli",
        text=text,
        status=WriteQueueStatus.failed,
        attempts=attempts,
        error="boom",
    )


def test_retry_failed_requeues_all(factory):
    db = factory()
    db.add(_failed_job(project="proj-a"))
    db.add(_failed_job(project="proj-b", text="other"))
    db.add(
        WriteQueueJob(
            project="proj-a",
            hostname="host1",
            client_name="cli",
            text="ok",
            status=WriteQueueStatus.done,
            attempts=1,
        )
    )
    db.commit()
    db.close()

    client = make_client(factory)
    resp = client.post("/admin/write-queue/retry-failed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["requeued"] == 2
    assert set(body["projects"]) == {"proj-a", "proj-b"}

    db = factory()
    failed = (
        db.query(WriteQueueJob)
        .filter(WriteQueueJob.status == WriteQueueStatus.failed)
        .count()
    )
    queued = (
        db.query(WriteQueueJob)
        .filter(WriteQueueJob.status == WriteQueueStatus.queued)
        .count()
    )
    row = (
        db.query(WriteQueueJob)
        .filter(WriteQueueJob.text == "hello")
        .one()
    )
    db.close()
    assert failed == 0
    assert queued == 2
    assert row.attempts == 0
    assert row.error == "reprocessamento manual (admin)"


def test_retry_failed_project_filter(factory):
    db = factory()
    db.add(_failed_job(project="proj-a"))
    db.add(_failed_job(project="proj-b", text="other"))
    db.commit()
    db.close()

    client = make_client(factory)
    resp = client.post(
        "/admin/write-queue/retry-failed", params={"project": "proj-a"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requeued"] == 1
    assert body["projects"] == ["proj-a"]

    db = factory()
    still_failed = (
        db.query(WriteQueueJob)
        .filter(
            WriteQueueJob.project == "proj-b",
            WriteQueueJob.status == WriteQueueStatus.failed,
        )
        .count()
    )
    db.close()
    assert still_failed == 1


def test_retry_failed_empty_returns_zero(factory):
    client = make_client(factory)
    resp = client.post("/admin/write-queue/retry-failed")
    assert resp.status_code == 200
    assert resp.json() == {"requeued": 0, "projects": []}
