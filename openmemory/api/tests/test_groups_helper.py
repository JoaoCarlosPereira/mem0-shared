"""Testes do helper de resolução hostname → grupo (task_02 / ADR-003)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Group, User
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
    # O helper usa app.database.SessionLocal; redireciona para a sessão de teste.
    monkeypatch.setattr("app.database.SessionLocal", Session)
    groups_mod.invalidate_group_cache()
    try:
        yield Session
    finally:
        groups_mod.invalidate_group_cache()
        engine.dispose()


def _seed_user_with_group(Session, hostname, group_name):
    s = Session()
    try:
        g = Group(name=group_name)
        s.add(g)
        s.flush()
        s.add(User(user_id=hostname, group=g))
        s.commit()
    finally:
        s.close()


def test_resolves_group_of_existing_user(session_factory):
    _seed_user_with_group(session_factory, "host-a", "Equipe A")
    assert groups_mod.group_of_hostname("host-a") == "Equipe A"


def test_unknown_hostname_returns_none(session_factory):
    assert groups_mod.group_of_hostname("inexistente") is None


def test_user_without_group_returns_none(session_factory):
    s = session_factory()
    try:
        s.add(User(user_id="host-sem-grupo"))
        s.commit()
    finally:
        s.close()
    assert groups_mod.group_of_hostname("host-sem-grupo") is None


def test_empty_hostname_returns_none(session_factory):
    assert groups_mod.group_of_hostname("") is None
    assert groups_mod.group_of_hostname(None) is None


def test_cache_hit_avoids_second_db_query(session_factory, monkeypatch):
    _seed_user_with_group(session_factory, "host-c", "Equipe C")
    calls = {"n": 0}
    real = groups_mod._query_group_name

    def _counting(hostname):
        calls["n"] += 1
        return real(hostname)

    monkeypatch.setattr(groups_mod, "_query_group_name", _counting)

    assert groups_mod.group_of_hostname("host-c") == "Equipe C"
    assert groups_mod.group_of_hostname("host-c") == "Equipe C"
    assert calls["n"] == 1, "segunda chamada dentro do TTL não deve consultar o banco"


def test_invalidate_forces_requery_and_reflects_new_group(session_factory, monkeypatch):
    _seed_user_with_group(session_factory, "host-d", "Equipe D")
    assert groups_mod.group_of_hostname("host-d") == "Equipe D"

    # Move o usuário para outro grupo diretamente no banco.
    s = session_factory()
    try:
        new_group = Group(name="Equipe Nova")
        s.add(new_group)
        s.flush()
        user = s.query(User).filter(User.user_id == "host-d").one()
        user.group_id = new_group.id
        s.commit()
    finally:
        s.close()

    # Sem invalidar: ainda serve o valor cacheado.
    assert groups_mod.group_of_hostname("host-d") == "Equipe D"
    # Após invalidar: reconsulta e reflete o novo grupo.
    groups_mod.invalidate_group_cache("host-d")
    assert groups_mod.group_of_hostname("host-d") == "Equipe Nova"


def test_hostname_normalized_consistently(session_factory):
    _seed_user_with_group(session_factory, "host-e", "Equipe E")
    # resolve_hostname faz trim; espaços ao redor devem resolver para o mesmo usuário.
    assert groups_mod.group_of_hostname("  host-e  ") == "Equipe E"


def test_query_failure_returns_none(session_factory, monkeypatch):
    def _boom(hostname):
        raise RuntimeError("db down")

    monkeypatch.setattr(groups_mod, "_query_group_name", _boom)
    assert groups_mod.group_of_hostname("qualquer") is None
