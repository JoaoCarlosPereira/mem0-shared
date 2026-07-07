"""Tests for fail-closed write guard (unregistered hostname rejection)."""

import json
import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import app.database as database_module
from app import mcp_server
from app.database import Base
from app.mcp_server import add_memories
from app.models import User, USER_TYPE_LEGACY_HOST, USER_TYPE_PERSON
from app.utils.write_guard import (
    WriteBlockedError,
    assert_write_allowed,
    unregistered_writes_allowed,
)


@pytest.fixture(autouse=True)
def _guard_enabled(monkeypatch):
    monkeypatch.delenv("MEM0_ALLOW_UNREGISTERED_WRITES", raising=False)


@pytest.fixture
def registered_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(database_module, "SessionLocal", Session)

    session = Session()
    person = User(
        user_id="google-sub-1",
        google_sub="google-sub-1",
        display_name="Jaíne Seibert",
        user_type=USER_TYPE_PERSON,
    )
    legacy = User(user_id="S0293", user_type=USER_TYPE_LEGACY_HOST)
    session.add_all([person, legacy])
    session.commit()
    session.close()
    yield Session
    engine.dispose()


class _FakeQueue:
    def __init__(self):
        self.jobs = []

    def enqueue(self, job):
        self.jobs.append(job)
        return "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"


@pytest.fixture
def fake_queue(monkeypatch):
    q = _FakeQueue()
    with patch.object(mcp_server, "write_queue", q):
        yield q


def test_guard_active_by_default():
    assert unregistered_writes_allowed() is False


def test_unknown_host_blocked():
    with pytest.raises(WriteBlockedError, match="unknown-host"):
        assert_write_allowed("unknown-host")


def test_unregistered_host_blocked(registered_db):
    with pytest.raises(WriteBlockedError, match="not registered"):
        assert_write_allowed("OTHER-PC")


def test_existing_hostname_allowed_without_google_link(registered_db):
    assert_write_allowed("S0293") is None


def test_agent_token_allowed_without_hostname_user(registered_db):
    session = registered_db()
    person = session.query(User).filter(User.user_type == USER_TYPE_PERSON).one()
    session.close()
    assert_write_allowed(
        "unknown-host",
        auth_method="agent_token",
        auth_user=str(person.id),
    ) is None


def test_agent_token_invalid_owner_blocked(registered_db):
    with pytest.raises(WriteBlockedError, match="agent token owner"):
        assert_write_allowed(
            "unknown-host",
            auth_method="agent_token",
            auth_user=str(uuid.uuid4()),
        )


def test_allow_unregistered_env(monkeypatch, registered_db):
    monkeypatch.setenv("MEM0_ALLOW_UNREGISTERED_WRITES", "1")
    assert unregistered_writes_allowed() is True
    assert_write_allowed("unknown-host") is None


@pytest.mark.asyncio
async def test_add_memories_rejects_unknown_host(fake_queue, registered_db):
    mcp_server.user_id_var.set("")
    mcp_server.client_name_var.set("claude-code")
    out = await add_memories("remember X", project="alpha")
    assert "memory write blocked" in out
    assert fake_queue.jobs == []


@pytest.mark.asyncio
async def test_add_memories_rejects_unregistered_host(fake_queue, registered_db):
    mcp_server.user_id_var.set("S0700")
    mcp_server.client_name_var.set("claude-code")
    out = await add_memories("remember X", project="alpha")
    assert "not registered" in out
    assert fake_queue.jobs == []


@pytest.mark.asyncio
async def test_add_memories_accepts_existing_hostname(fake_queue, registered_db):
    mcp_server.user_id_var.set("S0293")
    mcp_server.client_name_var.set("claude-code")
    out = await add_memories("remember X", project="alpha")
    assert json.loads(out)["status"] == "accepted"
    assert len(fake_queue.jobs) == 1
    assert fake_queue.jobs[0].hostname == "S0293"


@pytest.mark.asyncio
async def test_add_memories_accepts_agent_token_on_unknown_host(fake_queue, registered_db):
    session = registered_db()
    person = session.query(User).filter(User.user_type == USER_TYPE_PERSON).one()
    person_id = str(person.id)
    session.close()

    mcp_server.user_id_var.set("")
    mcp_server.client_name_var.set("claude-code")
    tok_method = mcp_server.auth_method_var.set("agent_token")
    tok_user = mcp_server.auth_user_var.set(person_id)
    try:
        out = await add_memories("remember X", project="alpha")
        assert json.loads(out)["status"] == "accepted"
        assert len(fake_queue.jobs) == 1
    finally:
        mcp_server.auth_method_var.reset(tok_method)
        mcp_server.auth_user_var.reset(tok_user)
