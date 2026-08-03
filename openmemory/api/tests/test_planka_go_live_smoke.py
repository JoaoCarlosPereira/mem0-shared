"""Go-live smoke: MCP pipeline + inventário Spec↔PLANKA (task_07)."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PLANKA_MIRROR_SYNC", "0")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_server
from app.database import Base
from app.mcp_server import (
    claim_task,
    create_spec_workspace,
    create_task,
    update_task_status,
    write_spec_document,
)
from app.models import SpecPlankaIdMap, TaskCard
from app.utils.planka import ENTITY_DOCUMENT, ENTITY_TASK
from app.utils.planka_resync import assert_inventory_gate, inventory_divergences, resync_all


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


@pytest.fixture(autouse=True)
def _wire(factory, monkeypatch):
    monkeypatch.setattr(mcp_server, "SessionLocal", factory)
    mcp_server.user_id_var.set("DESKTOP-SMOKE")
    mcp_server.client_name_var.set("cursor")
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    yield


class TestMcpPipelineSmoke:
    @pytest.mark.asyncio
    async def test_create_claim_status_write_document(self):
        ws = json.loads(
            await create_spec_workspace(
                "mem0-shared", f"smoke-{uuid4().hex[:8]}", "Smoke WS"
            )
        )
        task = json.loads(await create_task(ws["id"], "Smoke card", "corpo"))
        assert task["status"] == "tasks"

        claimed = json.loads(await claim_task(task["id"]))
        assert claimed["claimed"] is True
        version = claimed["version"]

        for status in ("revisao_codigo", "fase_teste", "concluido"):
            moved = json.loads(
                await update_task_status(task["id"], status, version)
            )
            assert moved.get("updated") is True, moved
            assert moved["status"] == status
            version = moved["version"]

        wrote = json.loads(
            await write_spec_document(ws["id"], "prd", "# PRD smoke", None)
        )
        assert wrote.get("conflict") is False
        assert wrote.get("version") == 1


class TestInventoryGate:
    def test_divergences_detect_gap(self):
        report = {
            "totals": {
                "spec_tasks": 2,
                "mirrored_tasks": 1,
                "planka_tasks_mapped": 1,
                "spec_documents": 1,
                "mirrored_documents": 1,
                "planka_documents_mapped": 1,
            },
            "errors": [],
        }
        issues = inventory_divergences(report)
        assert any("tasks" in i for i in issues)
        with pytest.raises(AssertionError):
            assert_inventory_gate(report)

    @pytest.mark.asyncio
    async def test_resync_inventory_passes_with_mock_mirror(self, factory):
        db = factory()
        try:
            ws = json.loads(
                await create_spec_workspace(
                    "mem0-shared", f"inv-{uuid4().hex[:8]}", "Inv WS"
                )
            )
            task = json.loads(await create_task(ws["id"], "T1"))
            await write_spec_document(ws["id"], "prd", "# x", None)

            # Simula id_map já alinhado + mirror client que não falha.
            from uuid import UUID

            tid = UUID(task["id"])
            wid = UUID(ws["id"])
            doc = (
                db.query(TaskCard).filter(TaskCard.id == tid).first()
            )  # just flush session
            _ = doc
            # Re-open for documents via mcp already committed; refresh maps.
            db.expire_all()
            from app.models import SpecDocument

            document = (
                db.query(SpecDocument)
                .filter(SpecDocument.workspace_id == wid)
                .first()
            )
            assert document is not None
            db.add(
                SpecPlankaIdMap(
                    entity_type=ENTITY_TASK, spec_id=tid, planka_id="p-task"
                )
            )
            db.add(
                SpecPlankaIdMap(
                    entity_type=ENTITY_DOCUMENT,
                    spec_id=document.id,
                    planka_id="p-doc",
                )
            )
            db.commit()

            client = MagicMock()
            client.ensure_workspace_board = AsyncMock(return_value="board-1")
            client.mirror_task = AsyncMock()
            client.mirror_document = AsyncMock()

            report = await resync_all(db, client=client)
            assert_inventory_gate(report)
        finally:
            db.close()
