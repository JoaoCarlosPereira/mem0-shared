"""Tests for LLM-assisted duplicate project merge governance."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.governance.project_merge import (
    MergeGroup,
    ProjectProfile,
    _parse_merge_groups,
    apply_project_merge,
    detect_duplicate_groups_with_llm,
    run_merge_projects_job,
)
from app.models import Base, GovernanceSchedule, Project, WriteAuditLog, WriteQueueJob, WriteQueueStatus
from app.models import GovernanceJobType

_MERGE_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "routers" / "governance_project_merge.py"
)
_spec = importlib.util.spec_from_file_location("governance_project_merge_under_test", _MERGE_PATH)
_governance_merge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_governance_merge)


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


class FakeLLM:
    def __init__(self, groups):
        self._groups = groups

    def generate_response(self, *, messages, response_format=None):
        return json.dumps({"groups": self._groups})


def test_parse_merge_groups_filters_unknown_projects():
    profiles = [
        ProjectProfile("sysmovs", 10, "host", []),
        ProjectProfile("sysmovs-delphi", 5, "host", []),
    ]
    raw = [
        {
            "canonical": "sysmovs",
            "aliases": ["sysmovs-delphi", "missing"],
            "confidence": 0.9,
            "reason": "same product",
        }
    ]
    groups = _parse_merge_groups(raw, profiles=profiles)
    assert len(groups) == 1
    assert groups[0].aliases == ["sysmovs-delphi"]


def test_detect_duplicate_groups_with_llm_threshold():
    profiles = [
        ProjectProfile("sysmovs", 288, "h1", ["Ark game"]),
        ProjectProfile("dsv-delphi-sysmovs", 43, "h2", ["Delphi module"]),
        ProjectProfile("default", 10, "h3", ["other"]),
    ]
    llm = FakeLLM(
        [
            {
                "canonical": "sysmovs",
                "aliases": ["dsv-delphi-sysmovs"],
                "confidence": 0.93,
                "reason": "same workspace",
            }
        ]
    )
    groups = detect_duplicate_groups_with_llm(profiles, llm, confidence_threshold=0.85)
    assert len(groups) == 1
    assert groups[0].canonical == "sysmovs"


def test_apply_project_merge_updates_sql_and_qdrant(factory):
    db = factory()
    db.add(Project(name="sysmovs"))
    db.add(Project(name="dsv-delphi-sysmovs", first_seen_hostname="dev"))
    db.add(
        WriteQueueJob(
            project="dsv-delphi-sysmovs",
            hostname="dev",
            client_name="cli",
            text="x",
            status=WriteQueueStatus.done,
        )
    )
    db.add(
        WriteAuditLog(
            project="dsv-delphi-sysmovs",
            hostname="dev",
            client_name="cli",
            action="enqueue",
        )
    )
    db.commit()

    vs = MagicMock()
    point = MagicMock()
    point.id = "mem-1"
    point.payload = {"project": "dsv-delphi-sysmovs", "data": "hello"}
    vs._create_filter.return_value = None
    vs.client.scroll.side_effect = [([point], None)]

    moved = apply_project_merge(
        db,
        vs,
        canonical="sysmovs",
        aliases=["dsv-delphi-sysmovs"],
        job_id="job-1",
    )
    assert moved == 1
    vs.update.assert_called_once()
    assert vs.update.call_args[0][0] == "mem-1"
    assert vs.update.call_args[1]["payload"]["project"] == "sysmovs"

    db = factory()
    assert db.query(Project).filter(Project.name == "dsv-delphi-sysmovs").first() is None
    assert (
        db.query(WriteQueueJob).filter(WriteQueueJob.project == "sysmovs").count() == 1
    )
    assert (
        db.query(WriteAuditLog).filter(WriteAuditLog.project == "sysmovs").count() == 1
    )
    db.close()


def test_apply_project_merge_merges_conflicting_governance_schedules(factory):
    """When both canonical and alias have schedules for the same job_type, merge safely."""
    import datetime

    db = factory()
    db.add(Project(name="sysmovs"))
    db.add(Project(name="dsv-delphi-sysmovs"))
    canonical_ts = datetime.datetime(2026, 6, 28, 12, 0, 0)
    alias_ts = datetime.datetime(2026, 6, 29, 0, 0, 0)
    db.add(
        GovernanceSchedule(
            job_type=GovernanceJobType.dedup,
            scope="sysmovs",
            last_run_at=canonical_ts,
        )
    )
    db.add(
        GovernanceSchedule(
            job_type=GovernanceJobType.dedup,
            scope="dsv-delphi-sysmovs",
            last_run_at=alias_ts,
        )
    )
    db.commit()

    vs = MagicMock()
    vs._create_filter.return_value = None
    vs.client.scroll.return_value = ([], None)

    apply_project_merge(
        db,
        vs,
        canonical="sysmovs",
        aliases=["dsv-delphi-sysmovs"],
        job_id="job-sched",
    )

    rows = db.query(GovernanceSchedule).filter(
        GovernanceSchedule.job_type == GovernanceJobType.dedup,
        GovernanceSchedule.scope.in_(["sysmovs", "dsv-delphi-sysmovs"]),
    ).all()
    assert len(rows) == 1
    assert rows[0].scope == "sysmovs"
    assert rows[0].last_run_at == alias_ts
    db.close()


def test_run_merge_projects_job_dry_run(factory, monkeypatch):
    db = factory()
    db.add(Project(name="sysmovs"))
    db.add(Project(name="sysmovs-delphi"))
    db.commit()
    db.close()

    monkeypatch.setattr(
        "app.governance.project_merge.collect_project_profiles",
        lambda _db: [
            ProjectProfile("sysmovs", 10, None, []),
            ProjectProfile("sysmovs-delphi", 5, None, []),
        ],
    )
    monkeypatch.setattr(
        "app.governance.project_merge.detect_duplicate_groups_with_llm",
        lambda profiles, llm, **kwargs: [
            MergeGroup("sysmovs", ["sysmovs-delphi"], 0.95, "same")
        ],
    )
    monkeypatch.setattr(
        "app.governance.project_merge.get_memory_client_safe",
        lambda: MagicMock(llm=FakeLLM([]), vector_store=MagicMock()),
        raising=False,
    )

    client = MagicMock()
    client.llm = FakeLLM([])
    client.vector_store = MagicMock()

    count = run_merge_projects_job(
        project=None,
        job_id="dry",
        session_factory=factory,
        memory_client_provider=lambda: client,
        payload={"dry_run": True},
    )
    assert count == 1
    client.vector_store.update.assert_not_called()


def test_merge_preview_endpoint(factory, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.database import get_db

    app = FastAPI()
    app.include_router(_governance_merge.router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override

    db = factory()
    db.add(Project(name="sysmovs"))
    db.add(Project(name="sysmovs-delphi"))
    db.commit()
    db.close()

    monkeypatch.setattr(
        _governance_merge,
        "preview_project_merges",
        lambda **kwargs: [
            {
                "canonical": "sysmovs",
                "aliases": ["sysmovs-delphi"],
                "confidence": 0.91,
                "reason": "same",
                "memory_counts": {"sysmovs": 10, "sysmovs-delphi": 5},
            }
        ],
    )
    client = TestClient(app)
    resp = client.get("/admin/governance/projects/merge-preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["groups"][0]["canonical"] == "sysmovs"
