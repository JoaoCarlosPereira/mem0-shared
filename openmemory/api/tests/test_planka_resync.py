"""Tests for Spec → PLANKA bootstrap/resync (task_03)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import Base  # noqa: F401 — load Base before models
from app.models import SpecDocument, SpecWorkspace, TaskCard
from app.utils.planka_resync import resync_all, resync_workspace


@pytest.mark.asyncio
async def test_resync_workspace_missing_returns_error():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = await resync_workspace(db, uuid.uuid4())
    assert result.spec_tasks == 0
    assert any("não encontrado" in e for e in result.errors)


@pytest.mark.asyncio
async def test_resync_empty_workspace_idempotent():
    workspace_id = uuid.uuid4()
    workspace = SimpleNamespace(
        id=workspace_id,
        project_id="mem0-shared",
        slug="empty",
        name="Empty",
    )
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is SpecWorkspace:
            q.filter.return_value.first.return_value = workspace
        elif model is TaskCard:
            q.filter.return_value.all.return_value = []
        elif model is SpecDocument:
            q.filter.return_value.all.return_value = []
        else:
            q.filter.return_value.first.return_value = None
            q.filter.return_value.all.return_value = []
            q.filter.return_value.count.return_value = 0
        return q

    db.query.side_effect = query_side_effect
    client = MagicMock()
    client.ensure_workspace_board = AsyncMock(return_value="board-1")
    client.mirror_task = AsyncMock()
    client.mirror_document = AsyncMock()

    first = await resync_workspace(db, workspace_id, client=client)
    second = await resync_workspace(db, workspace_id, client=client)

    assert first.spec_tasks == 0
    assert first.mirrored_tasks == 0
    assert first.errors == []
    assert second.errors == []
    assert client.ensure_workspace_board.await_count == 2
    client.mirror_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_resync_mirrors_tasks_and_documents():
    workspace_id = uuid.uuid4()
    task_id = uuid.uuid4()
    workspace = SimpleNamespace(id=workspace_id, slug="ws", name="WS", project_id="p")
    task = SimpleNamespace(id=task_id, workspace_id=workspace_id, title="T")
    document = SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        document_type=SimpleNamespace(value="prd"),
    )

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is SpecWorkspace:
            q.filter.return_value.first.return_value = workspace
            q.order_by.return_value.all.return_value = [workspace]
        elif model is TaskCard:
            q.filter.return_value.all.return_value = [task]
        elif model is SpecDocument:
            q.filter.return_value.all.return_value = [document]
        else:
            q.filter.return_value.count.return_value = 0
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side_effect
    client = MagicMock()
    client.ensure_workspace_board = AsyncMock(return_value="board-9")
    client.mirror_task = AsyncMock()
    client.mirror_document = AsyncMock()

    result = await resync_workspace(db, workspace_id, client=client)
    assert result.mirrored_tasks == 1
    assert result.mirrored_documents == 1
    client.mirror_task.assert_awaited_once_with(task_id)
    client.mirror_document.assert_awaited_once_with(workspace_id, "prd")

    report = await resync_all(db, client=client)
    assert report["totals"]["workspaces"] == 1
    assert report["totals"]["mirrored_tasks"] >= 1
