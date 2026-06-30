"""Testes do router /admin/groups (task_06 / ADR-002).

Usa TestClient + override de get_db sobre SQLite em memória (padrão
``test_admin_write_queue_retry.py``).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, DEFAULT_GROUP_NAME, Group, User
from app.routers.groups import router


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


def _seed_default(factory):
    s = factory()
    try:
        g = Group(name=DEFAULT_GROUP_NAME)
        s.add(g)
        s.commit()
        return str(g.id)
    finally:
        s.close()


def _seed_user(factory, hostname, group_id=None):
    import uuid as _uuid

    if isinstance(group_id, str):
        group_id = _uuid.UUID(group_id)
    s = factory()
    try:
        s.add(User(user_id=hostname, group_id=group_id))
        s.commit()
    finally:
        s.close()


def test_create_group(client):
    r = client.post("/admin/groups", json={"name": "Equipe X"})
    assert r.status_code == 201
    assert r.json()["name"] == "Equipe X"
    assert r.json()["member_count"] == 0


def test_create_duplicate_name_case_insensitive_returns_409(client):
    client.post("/admin/groups", json={"name": "Equipe X"})
    r = client.post("/admin/groups", json={"name": "equipe x"})
    assert r.status_code == 409


def test_create_empty_name_returns_400(client):
    r = client.post("/admin/groups", json={"name": "   "})
    assert r.status_code == 400


def test_list_groups_returns_member_count(client, factory):
    gid = client.post("/admin/groups", json={"name": "Equipe Y"}).json()["id"]
    _seed_user(factory, "host-1", group_id=gid)
    _seed_user(factory, "host-2", group_id=gid)

    r = client.get("/admin/groups")
    assert r.status_code == 200
    groups = {g["name"]: g for g in r.json()["groups"]}
    assert groups["Equipe Y"]["member_count"] == 2


def test_rename_group(client):
    gid = client.post("/admin/groups", json={"name": "Antigo"}).json()["id"]
    r = client.put(f"/admin/groups/{gid}", json={"name": "Novo"})
    assert r.status_code == 200
    assert r.json()["name"] == "Novo"


def test_rename_to_existing_name_returns_409(client):
    client.post("/admin/groups", json={"name": "A"})
    gid = client.post("/admin/groups", json={"name": "B"}).json()["id"]
    r = client.put(f"/admin/groups/{gid}", json={"name": "a"})
    assert r.status_code == 409


def test_delete_group_with_members_returns_400(client, factory):
    gid = client.post("/admin/groups", json={"name": "ComMembros"}).json()["id"]
    _seed_user(factory, "host-x", group_id=gid)
    r = client.delete(f"/admin/groups/{gid}")
    assert r.status_code == 400


def test_delete_default_group_returns_403(client, factory):
    gid = _seed_default(factory)
    r = client.delete(f"/admin/groups/{gid}")
    assert r.status_code == 403


def test_delete_empty_group_succeeds(client):
    gid = client.post("/admin/groups", json={"name": "Vazio"}).json()["id"]
    r = client.delete(f"/admin/groups/{gid}")
    assert r.status_code == 200


def test_delete_missing_group_returns_404(client):
    import uuid as _uuid

    r = client.delete(f"/admin/groups/{_uuid.uuid4()}")
    assert r.status_code == 404


def test_add_member_moves_user_and_invalidates_cache(client, factory, monkeypatch):
    calls = {"hosts": []}
    monkeypatch.setattr(
        "app.routers.groups.invalidate_group_cache",
        lambda host=None: calls["hosts"].append(host),
    )
    gid = client.post("/admin/groups", json={"name": "Destino"}).json()["id"]
    _seed_user(factory, "host-move")

    r = client.post(f"/admin/groups/{gid}/members", json={"user_id": "host-move"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "host-move"
    assert "host-move" in calls["hosts"]

    members = client.get(f"/admin/groups/{gid}/members").json()["members"]
    assert any(m["user_id"] == "host-move" for m in members)


def test_add_member_unknown_user_returns_404(client):
    gid = client.post("/admin/groups", json={"name": "Z"}).json()["id"]
    r = client.post(f"/admin/groups/{gid}/members", json={"user_id": "nao-existe"})
    assert r.status_code == 404


def test_remove_member_moves_to_default(client, factory, monkeypatch):
    monkeypatch.setattr("app.routers.groups.invalidate_group_cache", lambda host=None: None)
    _seed_default(factory)
    gid = client.post("/admin/groups", json={"name": "Origem"}).json()["id"]
    _seed_user(factory, "host-rm", group_id=gid)

    r = client.delete(f"/admin/groups/{gid}/members/host-rm")
    assert r.status_code == 200

    # O membro saiu do grupo de origem...
    members = client.get(f"/admin/groups/{gid}/members").json()["members"]
    assert all(m["user_id"] != "host-rm" for m in members)
    # ...e foi para o Default.
    groups = {g["name"]: g for g in client.get("/admin/groups").json()["groups"]}
    default_id = groups[DEFAULT_GROUP_NAME]["id"]
    default_members = client.get(f"/admin/groups/{default_id}/members").json()["members"]
    assert any(m["user_id"] == "host-rm" for m in default_members)
