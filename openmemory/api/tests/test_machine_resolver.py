"""Testes de resolução canônica de máquinas e vínculo legado."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database_module
from app.database import Base
from app.models import USER_TYPE_LEGACY_HOST, Machine, MachineStatus, User
from app.utils.machine_resolver import (
    canonical_machine_hostname,
    find_machine,
    resolve_or_create_machine,
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
    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_canonical_machine_hostname_uppercases_sysmo():
    assert canonical_machine_hostname("s0281") == "S0281"
    assert canonical_machine_hostname("  S0293 ") == "S0293"


def test_resolve_or_create_merges_lowercase_duplicate(db_session):
    legacy = User(user_id="S0350", user_type=USER_TYPE_LEGACY_HOST)
    db_session.add(legacy)
    db_session.add(
        Machine(hostname="s0350", status=MachineStatus.unlinked, legacy_user_id=None)
    )
    db_session.add(
        Machine(
            hostname="S0350",
            status=MachineStatus.unlinked,
            legacy_user_id=legacy.id,
        )
    )
    db_session.commit()

    machine, legacy_user = resolve_or_create_machine(db_session, "s0350")
    db_session.commit()

    assert machine.hostname == "S0350"
    assert legacy_user is not None
    assert machine.legacy_user_id == legacy.id
    assert db_session.query(Machine).count() == 1


def test_resolve_or_create_renames_orphan_lowercase_row(db_session):
    legacy = User(user_id="S0350", user_type=USER_TYPE_LEGACY_HOST)
    db_session.add(legacy)
    db_session.add(
        Machine(hostname="s0350", status=MachineStatus.unlinked, legacy_user_id=None)
    )
    db_session.commit()

    machine, legacy_user = resolve_or_create_machine(db_session, "S0350")
    db_session.commit()

    assert machine.hostname == "S0350"
    assert machine.legacy_user_id == legacy.id
    assert db_session.query(Machine).filter(Machine.hostname == "S0350").count() == 1


def test_find_machine_case_insensitive(db_session):
    db_session.add(Machine(hostname="S0272", status=MachineStatus.unlinked))
    db_session.commit()
    assert find_machine(db_session, "s0272").hostname == "S0272"


def test_consolidate_legacy_host_users_merges_case_variants(db_session):
    from app.models import Group

    group = Group(name="Dev")
    db_session.add(group)
    db_session.flush()
    upper = User(user_id="Hermes", user_type=USER_TYPE_LEGACY_HOST, group_id=group.id)
    lower = User(user_id="hermes", user_type=USER_TYPE_LEGACY_HOST, group_id=group.id)
    db_session.add_all([upper, lower])
    db_session.commit()

    from app.utils.machine_resolver import consolidate_legacy_host_users

    merged = consolidate_legacy_host_users(db_session, "hermes")
    db_session.commit()

    assert merged is not None
    assert merged.user_id == "Hermes"
    assert db_session.query(User).filter(User.user_type == USER_TYPE_LEGACY_HOST).count() == 1


def test_find_machine_case_insensitive_generic_hostname(db_session):
    db_session.add(Machine(hostname="Hermes", status=MachineStatus.unlinked))
    db_session.commit()
    assert find_machine(db_session, "hermes").hostname == "Hermes"
