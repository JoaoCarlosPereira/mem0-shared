"""Unit tests for PLANKA → Spec card-move bridge (ADR-007)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Project, SpecPlankaIdMap, SpecWorkspace, TaskCard, TaskCardStatus
from app.routers.specs import router as specs_router
from app.utils.planka import ENTITY_TASK, list_entity_type
from app.utils.planka_bridge import PlankaBridgeError, apply_planka_card_move
from app.utils.task_lock import UpdateTaskStatusResult


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
def bridge_client(factory, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    monkeypatch.setenv("PLANKA_INTERNAL_ACCESS_TOKEN", "bridge-secret")
    monkeypatch.delenv("INTERNAL_ACCESS_TOKEN", raising=False)

    app = FastAPI()
    app.include_router(specs_router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app), factory


def _mk_workspace(db) -> SpecWorkspace:
    if not db.query(Project).filter(Project.name == "mem0-shared").first():
        db.add(Project(name="mem0-shared"))
        db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug="bridge-ws", name="Bridge")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _map(db, entity_type, spec_id, planka_id):
    row = SpecPlankaIdMap(
        entity_type=entity_type,
        spec_id=spec_id,
        planka_id=planka_id,
    )
    db.add(row)
    db.commit()
    return row


def _seed_mapped_task(db, *, status=TaskCardStatus.tasks, assignee=None):
    ws = _mk_workspace(db)
    task = TaskCard(
        id=uuid4(),
        workspace_id=ws.id,
        title="Bridge task",
        status=status,
        version=1,
        assignee=assignee,
    )
    db.add(task)
    db.commit()
    _map(db, ENTITY_TASK, task.id, "pcard-1")
    _map(db, list_entity_type("tasks"), ws.id, "plist-tasks")
    _map(db, list_entity_type("em_andamento"), ws.id, "plist-em")
    _map(db, list_entity_type("revisao_codigo"), ws.id, "plist-rev")
    return ws, task


def test_unmapped_card_is_ignored(db_session):
    result = apply_planka_card_move(
        db_session,
        planka_card_id="planka-card-x",
        planka_list_id="list-x",
        actor="host-a",
    )
    assert result["applied"] is False
    assert result["reason"] == "not_mapped"


def test_claim_from_tasks_list(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    _, task = _seed_mapped_task(db_session)

    result = apply_planka_card_move(
        db_session,
        planka_card_id="pcard-1",
        planka_list_id="plist-em",
        actor="host-a",
    )
    assert result["applied"] is True
    assert result["action"] == "claim"
    assert result["version"] == 2
    db_session.refresh(task)
    assert task.status == TaskCardStatus.em_andamento
    assert task.assignee == "host-a"


def test_release_back_to_tasks_list(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    _, task = _seed_mapped_task(
        db_session, status=TaskCardStatus.em_andamento, assignee="host-a"
    )

    result = apply_planka_card_move(
        db_session,
        planka_card_id="pcard-1",
        planka_list_id="plist-tasks",
        actor="host-a",
    )
    assert result["applied"] is True
    assert result["action"] == "release"
    db_session.refresh(task)
    assert task.status == TaskCardStatus.tasks
    assert task.assignee is None


def test_status_advance_maps_list_to_spec(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    _, task = _seed_mapped_task(
        db_session, status=TaskCardStatus.em_andamento, assignee="host-a"
    )

    result = apply_planka_card_move(
        db_session,
        planka_card_id="pcard-1",
        planka_list_id="plist-rev",
        actor="host-a",
    )
    assert result["applied"] is True
    assert result["action"] == "status"
    assert result["status"] == "revisao_codigo"
    assert result["version"] == 2
    db_session.refresh(task)
    assert task.status == TaskCardStatus.revisao_codigo


def test_noop_when_already_on_target_list(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    _, task = _seed_mapped_task(
        db_session, status=TaskCardStatus.em_andamento, assignee="host-a"
    )

    result = apply_planka_card_move(
        db_session,
        planka_card_id="pcard-1",
        planka_list_id="plist-em",
        actor="host-a",
    )
    assert result["applied"] is False
    assert result["reason"] == "noop"
    assert result["version"] == task.version


def test_status_occ_conflict_raises(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    _seed_mapped_task(
        db_session, status=TaskCardStatus.em_andamento, assignee="host-a"
    )

    with patch(
        "app.utils.planka_bridge.update_task_status",
        return_value=UpdateTaskStatusResult(
            updated=False,
            conflict=True,
            version=9,
            status="em_andamento",
            current_assignee="host-a",
        ),
    ):
        with pytest.raises(PlankaBridgeError) as exc:
            apply_planka_card_move(
                db_session,
                planka_card_id="pcard-1",
                planka_list_id="plist-rev",
                actor="host-a",
            )
    assert exc.value.code == "status_conflict"
    assert exc.value.status_code == 409


def test_unknown_list_raises(db_session):
    ws = _mk_workspace(db_session)
    task = TaskCard(
        id=uuid4(),
        workspace_id=ws.id,
        title="x",
        status=TaskCardStatus.tasks,
        version=1,
    )
    db_session.add(task)
    db_session.commit()
    _map(db_session, ENTITY_TASK, task.id, "pcard-2")

    with pytest.raises(PlankaBridgeError) as exc:
        apply_planka_card_move(
            db_session,
            planka_card_id="pcard-2",
            planka_list_id="unknown-list",
            actor="host-a",
        )
    assert exc.value.code == "unknown_list"


class TestCardMovedHttpEndpoint:
    def test_accepts_planka_internal_bearer(self, bridge_client):
        client, factory = bridge_client
        db = factory()
        try:
            _seed_mapped_task(db)
        finally:
            db.close()

        resp = client.post(
            "/api/v1/specs/planka/card-moved",
            headers={"authorization": "Bearer bridge-secret"},
            json={
                "planka_card_id": "pcard-1",
                "planka_list_id": "plist-em",
                "actor": "host-a",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is True
        assert body["action"] == "claim"
        assert body["status"] == "em_andamento"
        assert body["version"] == 2

    def test_rejects_wrong_bridge_token(self, bridge_client):
        client, _ = bridge_client
        resp = client.post(
            "/api/v1/specs/planka/card-moved",
            headers={"authorization": "Bearer wrong-token"},
            json={
                "planka_card_id": "pcard-1",
                "planka_list_id": "plist-em",
                "actor": "host-a",
            },
        )
        assert resp.status_code == 401

    def test_rejects_missing_authorization(self, bridge_client):
        client, _ = bridge_client
        resp = client.post(
            "/api/v1/specs/planka/card-moved",
            json={
                "planka_card_id": "pcard-1",
                "planka_list_id": "plist-em",
            },
        )
        assert resp.status_code == 401
