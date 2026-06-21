"""Tests for the admin dashboard endpoints (Interface Admin / task_02).

Exercises GET /admin/overview, /admin/write-queue and /admin/write-audit against
in-memory SQLite via a FastAPI dependency override. Imports the admin router
directly (path-load) to avoid the heavy app.routers package __init__.
"""

import importlib.util
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import (
    Base,
    GovernanceJob,
    GovernanceJobStatus,
    GovernanceJobType,
    WriteAuditLog,
    WriteQueueJob,
    WriteQueueStatus,
)

# Path-load the router module directly: importing it via the app.routers package
# would pull heavy deps (fastapi_pagination, an import-time OpenAI client) not
# installed outside Docker. admin.py's own imports are light.
_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "admin.py"
_spec = importlib.util.spec_from_file_location("admin_dashboard_under_test", _PATH)
_admin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_admin)
router = _admin.router


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


def _wq(project="proj-x", hostname="host1", status=WriteQueueStatus.queued, text="hello", attempts=0):
    return WriteQueueJob(
        project=project,
        hostname=hostname,
        client_name="cli",
        text=text,
        status=status,
        attempts=attempts,
    )


# --------------------------------------------------------------------------- #
# overview
# --------------------------------------------------------------------------- #
def test_overview_empty_db_all_zeros(factory):
    client = make_client(factory)
    resp = client.get("/admin/overview")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "total_projects",
        "total_memories",
        "memories_last_24h",
        "write_queue_queued",
        "write_queue_processing",
        "write_queue_failed",
        "governance_queue_queued",
        "governance_queue_processing",
        "governance_queue_failed",
    ):
        assert body[key] == 0


def test_overview_three_failed_write_jobs(factory):
    db = factory()
    for _ in range(3):
        db.add(_wq(status=WriteQueueStatus.failed))
    db.add(_wq(status=WriteQueueStatus.queued))
    db.add(
        GovernanceJob(
            job_type=GovernanceJobType.dedup, status=GovernanceJobStatus.failed
        )
    )
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/overview").json()
    assert body["write_queue_failed"] == 3
    assert body["write_queue_queued"] == 1
    assert body["governance_queue_failed"] == 1


# --------------------------------------------------------------------------- #
# write-queue
# --------------------------------------------------------------------------- #
def test_write_queue_no_filter_returns_all_desc(factory):
    db = factory()
    db.add(_wq(text="older"))
    db.commit()
    db.add(_wq(text="newer"))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-queue").json()
    assert body["total"] == 2
    # newest first
    assert body["items"][0]["text_preview"] == "newer"


def test_write_queue_status_filter(factory):
    db = factory()
    db.add(_wq(status=WriteQueueStatus.failed))
    db.add(_wq(status=WriteQueueStatus.queued))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-queue", params={"status": "failed"}).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


def test_write_queue_invalid_status_400(factory):
    client = make_client(factory)
    resp = client.get("/admin/write-queue", params={"status": "bogus"})
    assert resp.status_code == 400


def test_write_queue_project_filter(factory):
    db = factory()
    db.add(_wq(project="proj-a"))
    db.add(_wq(project="proj-b"))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-queue", params={"project": "proj-a"}).json()
    assert body["total"] == 1
    assert body["items"][0]["project"] == "proj-a"


def test_write_queue_text_preview_truncated(factory):
    db = factory()
    db.add(_wq(text="A" * 500))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-queue").json()
    assert len(body["items"][0]["text_preview"]) == 120


def test_write_queue_pagination(factory):
    db = factory()
    for i in range(12):
        db.add(_wq(text=f"job-{i}"))
        db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-queue", params={"page": 2, "page_size": 5}).json()
    assert body["total"] == 12
    assert body["page"] == 2
    assert body["pages"] == 3
    assert len(body["items"]) == 5


def test_write_queue_failed_count_reflects_total_not_page(factory):
    db = factory()
    for _ in range(7):
        db.add(_wq(status=WriteQueueStatus.failed))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-queue", params={"page_size": 2}).json()
    assert len(body["items"]) == 2
    assert body["failed_count"] == 7


def test_write_queue_empty_pages_zero(factory):
    client = make_client(factory)
    body = client.get("/admin/write-queue").json()
    assert body["total"] == 0
    assert body["pages"] == 0
    assert body["items"] == []


# --------------------------------------------------------------------------- #
# write-audit
# --------------------------------------------------------------------------- #
def test_write_audit_date_filter(factory):
    db = factory()
    old = WriteAuditLog(
        project="p", hostname="h", action="enqueue",
        created_at=datetime(2020, 1, 1),
    )
    new = WriteAuditLog(
        project="p", hostname="h", action="enqueue",
        created_at=datetime(2030, 1, 1),
    )
    db.add(old)
    db.add(new)
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get(
        "/admin/write-audit",
        params={"from_date": "2025-01-01T00:00:00", "to_date": "2031-01-01T00:00:00"},
    ).json()
    assert body["total"] == 1


def test_write_audit_csv_export(factory):
    db = factory()
    db.add(WriteAuditLog(project="p", hostname="h", action="enqueue"))
    db.commit()
    db.close()

    client = make_client(factory)
    resp = client.get("/admin/write-audit", headers={"accept": "text/csv"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment; filename=audit.csv" in resp.headers["content-disposition"]
    assert "id,job_id,project,hostname,client_name,action,created_at" in resp.text


def test_write_audit_csv_over_10000_returns_400(factory):
    db = factory()
    db.bulk_save_objects(
        [
            WriteAuditLog(project="p", hostname="h", action="enqueue")
            for _ in range(10001)
        ]
    )
    db.commit()
    db.close()

    client = make_client(factory)
    resp = client.get("/admin/write-audit", headers={"accept": "text/csv"})
    assert resp.status_code == 400


def test_write_audit_json_pagination(factory):
    db = factory()
    db.bulk_save_objects(
        [WriteAuditLog(project="p", hostname="h", action="enqueue") for _ in range(5)]
    )
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/write-audit", params={"page_size": 2}).json()
    assert body["total"] == 5
    assert body["pages"] == 3
    assert len(body["items"]) == 2
