"""Testes da atribuição de grupo na criação do usuário e da normalização (task_05).

Cobre os helpers ``ensure_user_group``/``get_or_create_group``/``normalize_group_name``
e a regra ADR-004 (URL define só na criação; admin prevalece).
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
    """Retorna (existe, nome_do_grupo) lendo dentro da sessão (evita lazy-load detached)."""
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


def test_get_or_create_group_is_case_insensitive(session_factory):
    s = session_factory()
    try:
        g1 = groups_mod.get_or_create_group(s, "Equipe X")
        s.commit()
        g2 = groups_mod.get_or_create_group(s, "equipe x")  # mesma, outra caixa
        s.commit()
        assert g1.id == g2.id
        assert s.query(Group).filter(Group.name == "Equipe X").count() == 1
    finally:
        s.close()


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
    # Cria com Equipe A...
    groups_mod.ensure_user_group("host-fixo", "Equipe A")
    # ...reconecta informando Equipe B: NÃO deve sobrescrever (admin prevalece).
    groups_mod.ensure_user_group("host-fixo", "Equipe B")
    _, group_name = _user_group_name(session_factory, "host-fixo")
    assert group_name == "Equipe A"


def test_groupless_existing_user_gets_group_assigned(session_factory):
    # Simula linha criada por outro caminho (get_or_create_user) sem grupo.
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
    exists, _ = _user_group_name(session_factory, "host-trim")
    assert exists
