"""Testes da exposição do grupo do autor na lista de memórias (task_09)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import App, Group, Memory, User
from app.routers.memories import memory_group_name


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


def _memory_with(session, hostname, group_name=None):
    group = None
    if group_name is not None:
        group = Group(name=group_name)
        session.add(group)
        session.flush()
    user = User(user_id=hostname, group_id=group.id if group else None)
    session.add(user)
    session.flush()
    app = App(owner_id=user.id, name="cli")
    session.add(app)
    session.flush()
    mem = Memory(user_id=user.id, app_id=app.id, content="x")
    session.add(mem)
    session.commit()
    return session.query(Memory).filter(Memory.id == mem.id).one()


def test_memory_group_name_returns_author_group(session):
    mem = _memory_with(session, "host-a", "Equipe A")
    assert memory_group_name(mem) == "Equipe A"


def test_memory_group_name_none_when_user_has_no_group(session):
    mem = _memory_with(session, "host-b", None)
    assert memory_group_name(mem) is None


def test_memory_response_includes_group_field():
    # O schema deve expor `group` opcional (default None).
    from app.schemas import MemoryResponse

    assert "group" in MemoryResponse.model_fields
    assert MemoryResponse.model_fields["group"].default is None
