"""Testes do cadastro de usuário e vínculo de grupo na instalação (task_05 / ADR-004).

``?group=`` na URL MCP vincula equipe na primeira conexão; Admin prevalece depois.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import DEFAULT_GROUP_NAME, Group, User
from app.utils import groups as groups_mod


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr("app.database.SessionLocal", Session)
    groups_mod.invalidate_group_cache()
    try:
        yield Session
    finally:
        groups_mod.invalidate_group_cache()
        engine.dispose()


def _user_group_name(Session, hostname):
    s = Session()
    try:
        user = s.query(User).filter(User.user_id == hostname).first()
        if user is None:
            return False, None
        return True, (user.group.name if user.group is not None else None)
    finally:
        s.close()


def test_normalize_group_name():
    assert groups_mod.normalize_group_name("  Equipe X  ") == "Equipe X"
    assert groups_mod.normalize_group_name("") is None
    assert groups_mod.normalize_group_name(None) is None


def test_new_user_created_with_informed_group(session_factory):
    groups_mod.ensure_user_group("host-novo", "Equipe Backend")
    exists, group_name = _user_group_name(session_factory, "host-novo")
    assert exists
    assert group_name == "Equipe Backend"


def test_new_user_without_group_falls_back_to_default(session_factory):
    groups_mod.ensure_user_group("host-sem", None)
    _, group_name = _user_group_name(session_factory, "host-sem")
    assert group_name == DEFAULT_GROUP_NAME


def test_existing_user_with_group_is_not_overwritten(session_factory):
    groups_mod.ensure_user_group("host-fixo", "Equipe A")
    groups_mod.ensure_user_group("host-fixo", "Equipe B")
    _, group_name = _user_group_name(session_factory, "host-fixo")
    assert group_name == "Equipe A"


def test_groupless_existing_user_gets_group_from_install_url(session_factory):
    s = session_factory()
    try:
        s.add(User(user_id="host-orfao"))
        s.commit()
    finally:
        s.close()
    groups_mod.ensure_user_group("host-orfao", "Equipe C")
    _, group_name = _user_group_name(session_factory, "host-orfao")
    assert group_name == "Equipe C"


def test_hostname_normalized_on_create(session_factory):
    groups_mod.ensure_user_group("  host-trim  ", "Equipe D")
    exists, group_name = _user_group_name(session_factory, "host-trim")
    assert exists
    assert group_name == "Equipe D"


def test_requester_group_for_mcp_registers_and_returns_group(session_factory):
    s = session_factory()
    try:
        g = Group(name="Fiscal")
        s.add(g)
        s.flush()
        s.add(User(user_id="S0293", group_id=g.id))
        s.commit()
    finally:
        s.close()
    assert groups_mod.requester_group_for_mcp("S0293") == "Fiscal"
