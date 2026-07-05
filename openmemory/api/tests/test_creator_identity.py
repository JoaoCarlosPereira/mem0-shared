"""Tests for creator identity enrichment (hostname → linked person)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database_module
from app.database import Base
from app.models import Machine, MachineStatus, User, USER_TYPE_LEGACY_HOST, USER_TYPE_PERSON
from app.utils.creator_identity import (
    enrich_actor_items,
    enrich_memory_items,
    resolve_creator_identities,
)


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database_module, "SessionLocal", Session)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def linked_machine_setup(db_session):
    person = User(
        user_id="google-sub-1",
        google_sub="google-sub-1",
        display_name="João Silva",
        avatar_url="https://example.com/avatar.png",
        user_type=USER_TYPE_PERSON,
    )
    legacy = User(user_id="S0293", user_type=USER_TYPE_LEGACY_HOST)
    db_session.add_all([person, legacy])
    db_session.flush()

    machine = Machine(
        hostname="S0293",
        linked_user_id=person.id,
        legacy_user_id=legacy.id,
        status=MachineStatus.linked,
    )
    db_session.add(machine)
    db_session.commit()
    return person


def test_resolve_creator_identities_returns_linked_person(linked_machine_setup):
    identities = resolve_creator_identities(["S0293", "UNKNOWN"])
    assert "S0293" in identities
    assert identities["S0293"].display_name == "João Silva"
    assert identities["S0293"].avatar_url == "https://example.com/avatar.png"
    assert "UNKNOWN" not in identities


def test_enrich_memory_items_attaches_display_fields(linked_machine_setup):
    items = [
        {"created_by_hostname": "S0293", "created_by_client": "cursor"},
        {"created_by_hostname": "OTHER", "created_by_client": "claude"},
    ]
    enrich_memory_items(items)
    assert items[0]["created_by_display_name"] == "João Silva"
    assert items[0]["created_by_avatar_url"] == "https://example.com/avatar.png"
    assert "created_by_display_name" not in items[1]


def test_enrich_actor_items_uses_custom_keys(linked_machine_setup):
    items = [{"hostname": "S0293", "client_name": "cursor"}]
    enrich_actor_items(
        items,
        display_name_key="user_display_name",
        avatar_url_key="user_avatar_url",
    )
    assert items[0]["user_display_name"] == "João Silva"
    assert items[0]["user_avatar_url"] == "https://example.com/avatar.png"
