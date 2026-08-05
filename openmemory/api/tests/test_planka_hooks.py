"""Tests for PLANKA_MIRROR_SYNC hooks (task_04)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Project, SpecWorkspace, SpecWorkspaceStatus, TaskCard, TaskCardStatus
from app.utils import planka_hooks
from app.utils.planka import PlankaMirrorError
from app.utils.task_lock import claim_task, release_task, update_task_status


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


def _mk_task(db, **kwargs):
    if not db.query(Project).filter(Project.name == "mem0-shared").first():
        db.add(Project(name="mem0-shared"))
        db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug="hooks-ws", name="Hooks")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    task = TaskCard(
        workspace_id=ws.id,
        title="Mirror hooks",
        status=TaskCardStatus.tasks,
        **kwargs,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_mirror_disabled_is_noop(monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    db = MagicMock()
    with patch("app.utils.planka_hooks.PlankaMirrorHttpClient") as cls:
        planka_hooks.mirror_task(db, uuid4())
        cls.assert_not_called()


def test_mirror_enabled_calls_client(monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    db = MagicMock()
    client = MagicMock()
    client.mirror_task = AsyncMock()
    with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
        planka_hooks.mirror_task(db, uuid4())
    client.mirror_task.assert_awaited()


def test_mirror_failure_raises_http_502(monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    db = MagicMock()
    client = MagicMock()
    client.mirror_task = AsyncMock(side_effect=PlankaMirrorError(503, "down"))
    with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
        with pytest.raises(HTTPException) as exc:
            planka_hooks.mirror_task(db, uuid4())
    assert exc.value.status_code == 502
    assert exc.value.detail["mirror_failed"] is True


def test_claim_task_triggers_mirror_status(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    task = _mk_task(db_session)
    with patch("app.utils.planka_hooks.mirror_task_status") as mirror:
        result = claim_task(db_session, task.id, "host-a")
    assert result.claimed is True
    mirror.assert_called_once_with(db_session, task.id)


def test_release_task_triggers_mirror_status(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    task = _mk_task(db_session)
    claim_task(db_session, task.id, "host-a")
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    with patch("app.utils.planka_hooks.mirror_task_status") as mirror:
        release_task(db_session, task.id, "host-a", reason="test")
    mirror.assert_called_once_with(db_session, task.id)


def test_update_task_status_triggers_mirror_status(db_session, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    task = _mk_task(db_session)
    claimed = claim_task(db_session, task.id, "host-a")
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    with patch("app.utils.planka_hooks.mirror_task_status") as mirror:
        update_task_status(
            db_session,
            task.id,
            TaskCardStatus.revisao_codigo,
            claimed.version,
            "host-a",
        )
    mirror.assert_called_once_with(db_session, task.id)


class TestMirrorSetProjectLifecycle:
    """Tarefa kanban-archive-lifecycle: espelho isArchived/isCompleted."""

    def _mk_ws(self, db, *, status):
        if not db.query(Project).filter(Project.name == "mem0-shared").first():
            db.add(Project(name="mem0-shared"))
            db.commit()
        ws = SpecWorkspace(
            project_id="mem0-shared", slug="lifecycle-hooks-ws", name="Lifecycle", status=status
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws

    def test_disabled_is_noop(self, db_session, monkeypatch):
        monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
        ws = self._mk_ws(db_session, status=SpecWorkspaceStatus.concluido)
        with patch("app.utils.planka_hooks.PlankaMirrorHttpClient") as cls:
            planka_hooks.mirror_set_project_lifecycle(db_session, ws.id)
            cls.assert_not_called()

    def test_derives_flags_from_status_concluido(self, db_session, monkeypatch):
        monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
        ws = self._mk_ws(db_session, status=SpecWorkspaceStatus.concluido)
        client = MagicMock()
        client.set_project_lifecycle = AsyncMock()
        with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
            planka_hooks.mirror_set_project_lifecycle(db_session, ws.id)
        client.set_project_lifecycle.assert_awaited_once_with(
            ws.id, is_archived=False, is_completed=True
        )

    def test_derives_flags_from_status_arquivado(self, db_session, monkeypatch):
        monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
        ws = self._mk_ws(db_session, status=SpecWorkspaceStatus.arquivado)
        client = MagicMock()
        client.set_project_lifecycle = AsyncMock()
        with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
            planka_hooks.mirror_set_project_lifecycle(db_session, ws.id)
        client.set_project_lifecycle.assert_awaited_once_with(
            ws.id, is_archived=True, is_completed=True
        )

    def test_derives_flags_from_status_ativo(self, db_session, monkeypatch):
        monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
        ws = self._mk_ws(db_session, status=SpecWorkspaceStatus.ativo)
        client = MagicMock()
        client.set_project_lifecycle = AsyncMock()
        with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
            planka_hooks.mirror_set_project_lifecycle(db_session, ws.id)
        client.set_project_lifecycle.assert_awaited_once_with(
            ws.id, is_archived=False, is_completed=False
        )

    def test_best_effort_swallows_failure(self, db_session, monkeypatch):
        monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
        ws = self._mk_ws(db_session, status=SpecWorkspaceStatus.concluido)
        client = MagicMock()
        client.set_project_lifecycle = AsyncMock(side_effect=PlankaMirrorError(503, "down"))
        with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
            # não deve levantar
            planka_hooks.mirror_set_project_lifecycle_best_effort(db_session, ws.id)
