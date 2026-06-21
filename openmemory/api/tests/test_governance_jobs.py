"""Tests for GET /admin/governance/jobs (Interface Admin / task_03)."""

import os

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
)
from app.routers import governance as governance_router


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def make_client(factory):
    app = FastAPI()
    app.include_router(governance_router.router)

    def override_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _job(job_type=GovernanceJobType.dedup, status=GovernanceJobStatus.queued, project=None):
    return GovernanceJob(job_type=job_type, status=status, project=project)


def test_jobs_empty_db(factory):
    client = make_client(factory)
    body = client.get("/admin/governance/jobs").json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["failed_count"] == 0


def test_jobs_no_filter_desc(factory):
    db = factory()
    db.add(_job(project="first"))
    db.commit()
    db.add(_job(project="second"))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/governance/jobs").json()
    assert body["total"] == 2
    assert body["items"][0]["project"] == "second"  # newest first


def test_jobs_status_failed(factory):
    db = factory()
    db.add(_job(status=GovernanceJobStatus.failed))
    db.add(_job(status=GovernanceJobStatus.queued))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/governance/jobs", params={"status": "failed"}).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "failed"


def test_jobs_job_type_filter(factory):
    db = factory()
    db.add(_job(job_type=GovernanceJobType.dedup))
    db.add(_job(job_type=GovernanceJobType.ttl_prune))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/governance/jobs", params={"job_type": "dedup"}).json()
    assert body["total"] == 1
    assert body["items"][0]["job_type"] == "dedup"


def test_jobs_project_filter(factory):
    db = factory()
    db.add(_job(project="proj-x"))
    db.add(_job(project="proj-y"))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get("/admin/governance/jobs", params={"project": "proj-x"}).json()
    assert body["total"] == 1
    assert body["items"][0]["project"] == "proj-x"


def test_jobs_combined_status_and_job_type(factory):
    db = factory()
    db.add(_job(job_type=GovernanceJobType.ttl_prune, status=GovernanceJobStatus.queued))
    db.add(_job(job_type=GovernanceJobType.ttl_prune, status=GovernanceJobStatus.failed))
    db.add(_job(job_type=GovernanceJobType.dedup, status=GovernanceJobStatus.queued))
    db.commit()
    db.close()

    client = make_client(factory)
    body = client.get(
        "/admin/governance/jobs",
        params={"status": "queued", "job_type": "ttl_prune"},
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["job_type"] == "ttl_prune"
    assert body["items"][0]["status"] == "queued"


def test_jobs_failed_count_scope_ignores_status_filter(factory):
    db = factory()
    for _ in range(4):
        db.add(_job(job_type=GovernanceJobType.dedup, status=GovernanceJobStatus.failed))
    db.add(_job(job_type=GovernanceJobType.dedup, status=GovernanceJobStatus.queued))
    db.commit()
    db.close()

    client = make_client(factory)
    # filter by status=queued, but failed_count should still reflect the 4 failed
    body = client.get(
        "/admin/governance/jobs",
        params={"status": "queued", "job_type": "dedup", "page_size": 1},
    ).json()
    assert body["total"] == 1
    assert body["failed_count"] == 4


def test_jobs_invalid_status_400(factory):
    client = make_client(factory)
    assert client.get("/admin/governance/jobs", params={"status": "bogus"}).status_code == 400


def test_jobs_invalid_job_type_400(factory):
    client = make_client(factory)
    assert client.get("/admin/governance/jobs", params={"job_type": "bogus"}).status_code == 400
