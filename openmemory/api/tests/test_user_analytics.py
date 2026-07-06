"""Tests for /admin/analytics endpoints."""

from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, DEFAULT_GROUP_NAME, Group, Machine, MachineStatus, User, WriteAuditLog, WriteQueueJob
from app.models import USER_TYPE_LEGACY_HOST, USER_TYPE_PERSON
from app.read_audit_log_model import ReadAuditLog
from app.routers.user_analytics import router


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


@pytest.fixture
def client(factory):
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


def _seed_group_and_user(factory, hostname="alice-pc", group_name="Dev"):
    s = factory()
    try:
        default = Group(name=DEFAULT_GROUP_NAME)
        team = Group(name=group_name)
        s.add_all([default, team])
        s.flush()
        user = User(user_id=hostname, group_id=team.id)
        s.add(user)
        s.commit()
        return str(team.id), hostname
    finally:
        s.close()


def _seed_audit(factory, hostname="alice-pc"):
    import uuid as _uuid

    s = factory()
    try:
        now = datetime.utcnow()
        job_id = _uuid.uuid4()
        s.add(
            WriteQueueJob(
                id=job_id,
                project="proj-a",
                hostname=hostname,
                client_name="cursor",
                text="User prefers dark mode in the IDE",
            )
        )
        s.add(
            WriteAuditLog(
                job_id=job_id,
                project="proj-a",
                hostname=hostname,
                client_name="cursor",
                action="enqueue",
                created_at=now - timedelta(hours=1),
            )
        )
        s.add(
            ReadAuditLog(
                project="proj-a",
                memory_id="mem-1",
                access_type="search",
                source="mcp",
                hostname=hostname,
                client_name="cursor",
                accessed_at=now - timedelta(hours=2),
            )
        )
        s.commit()
    finally:
        s.close()


def test_list_groups_analytics_empty(client):
    r = client.get("/admin/analytics/groups")
    assert r.status_code == 200
    assert r.json()["groups"] == []


def test_group_analytics_with_member_stats(factory, client):
    group_id, hostname = _seed_group_and_user(factory)
    _seed_audit(factory, hostname)
    r = client.get(f"/admin/analytics/groups/{group_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["group"]["name"] == "Dev"
    assert body["group"]["member_count"] == 1
    assert body["group"]["writes_total"] == 1
    assert body["group"]["reads_total"] == 1
    assert len(body["members"]) == 1
    assert body["members"][0]["user_id"] == hostname
    assert body["members"][0]["usage_level"] == "ativo"


def test_group_analytics_shows_google_display_name_for_linked_machine(factory, client):
    group_id, hostname = _seed_group_and_user(factory, hostname="S0293")
    s = factory()
    try:
        person = User(
            user_id="google-sub-1",
            google_sub="google-sub-1",
            display_name="João Silva",
            user_type=USER_TYPE_PERSON,
        )
        legacy = s.query(User).filter(User.user_id == hostname).one()
        s.add(person)
        s.flush()
        s.add(
            Machine(
                hostname=hostname,
                linked_user_id=person.id,
                legacy_user_id=legacy.id,
                status=MachineStatus.linked,
            )
        )
        s.commit()
    finally:
        s.close()

    r = client.get(f"/admin/analytics/groups/{group_id}")
    assert r.status_code == 200
    member = r.json()["members"][0]
    assert member["user_id"] == hostname
    assert member["display_name"] == "João Silva"


def test_user_analytics_detail(factory, client):
    _, hostname = _seed_group_and_user(factory)
    _seed_audit(factory, hostname)
    r = client.get(f"/admin/analytics/users/{hostname}")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == hostname
    assert body["writes_total"] == 1
    assert body["reads_total"] == 1
    assert len(body["recent_writes"]) == 1
    assert body["recent_writes"][0]["text_preview"] == "User prefers dark mode in the IDE"
    assert len(body["recent_reads"]) == 1


def test_user_analytics_unregistered_hostname(factory, client):
    _seed_audit(factory, "ghost-pc")
    r = client.get("/admin/analytics/users/ghost-pc")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "ghost-pc"
    assert body["writes_total"] == 1


def test_user_analytics_ui_hostname_reads(factory, client):
    """Reads from the UI are stored as ui:{hostname} — must count toward user stats."""
    _, hostname = _seed_group_and_user(factory, hostname="alice-pc")
    s = factory()
    try:
        now = datetime.utcnow()
        s.add(
            ReadAuditLog(
                project="proj-a",
                memory_id="mem-ui-1",
                access_type="search",
                source="api",
                hostname=f"ui:{hostname}",
                client_name="openmemory",
                accessed_at=now,
            )
        )
        s.commit()
    finally:
        s.close()

    r = client.get(f"/admin/analytics/users/{hostname}")
    assert r.status_code == 200
    body = r.json()
    assert body["reads_total"] == 1
    assert body["reads_24h"] == 1
    assert len(body["recent_reads"]) == 1


def test_analytics_overview(factory, client):
    group_id, hostname = _seed_group_and_user(factory)
    _seed_audit(factory, hostname)
    r = client.get("/admin/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_users"] == 1
    assert body["total_groups"] == 2  # Default + Dev
    assert body["writes_total"] >= 1
    assert body["writes_24h"] >= 1
    assert body["writes_7d"] >= 1
    assert body["reads_total"] >= 1
    assert body["reads_24h"] >= 1
    assert body["reads_7d"] >= 1
