"""Testes do modelo Group e da FK users.group_id (task_01 / ADR-002).

Usa SQLite em memória via ``Base.metadata.create_all`` — o mesmo padrão dos demais
testes unitários da API (sem depender da cadeia Alembic).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base  # importado antes de app.models (ordem evita ciclo)
from app.models import DEFAULT_GROUP_NAME, Group, User


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def test_create_group_persists_and_is_queryable(session):
    g = Group(name="Equipe Backend")
    session.add(g)
    session.commit()

    fetched = session.query(Group).filter(Group.name == "Equipe Backend").one()
    assert fetched.id is not None
    assert fetched.name == "Equipe Backend"


def test_group_name_must_be_unique(session):
    session.add(Group(name="Equipe X"))
    session.commit()

    session.add(Group(name="Equipe X"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_group_relationship_navigates_both_ways(session):
    g = Group(name="Equipe Dados")
    u = User(user_id="host-1", group=g)
    session.add_all([g, u])
    session.commit()

    assert u.group is g
    assert u in g.members


def test_user_group_id_is_nullable(session):
    u = User(user_id="host-sem-grupo")
    session.add(u)
    session.commit()  # não deve levantar — group_id é opcional

    assert session.query(User).filter(User.user_id == "host-sem-grupo").one().group_id is None


def test_default_group_name_constant():
    assert DEFAULT_GROUP_NAME == "Default"
