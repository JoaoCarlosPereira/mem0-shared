"""Testes da task_07 (shared-specs): tools MCP de workspaces e documentos.

Padrão de ``test_mcp_write_enqueue.py``: monkeypatch de ``mcp_server.SessionLocal``
para um SQLite in-memory, ContextVars setadas, chamada das tools ``async`` e
parse do JSON de retorno. Cobrem idempotência, contrato de conflito e o
never-raise (exceção interna vira string ``"Error: ..."``).
"""

import json
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_server
from app.database import Base
from app.mcp_server import (
    create_spec_workspace,
    list_spec_workspaces,
    read_spec_document,
    search_specs,
    write_spec_document,
)


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
    mcp_server.user_id_var.set("DESKTOP-01")
    mcp_server.client_name_var.set("cursor")
    yield


class TestCreateAndList:
    @pytest.mark.asyncio
    async def test_create_workspace(self):
        out = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
        assert out["slug"] == "ws-1"
        assert out["created"] is True
        assert out["status"] == "planejamento"

    @pytest.mark.asyncio
    async def test_create_idempotente_por_slug(self):
        first = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
        second = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1 renomeada"))
        assert second["id"] == first["id"]
        assert second["created"] is False

    @pytest.mark.asyncio
    async def test_list_workspaces(self):
        await create_spec_workspace("mem0-shared", "ws-1", "WS 1")
        out = json.loads(await list_spec_workspaces("mem0-shared"))
        assert len(out) == 1
        assert out[0]["slug"] == "ws-1"


class TestWriteAndRead:
    @pytest.mark.asyncio
    async def test_ciclo_completo_create_write_read(self):
        ws = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
        w = json.loads(await write_spec_document(ws["id"], "prd", "# PRD v1", None))
        assert w["conflict"] is False
        assert w["version"] == 1

        r = json.loads(await read_spec_document(ws["id"], "prd"))
        assert r["found"] is True
        assert r["current_content"] == "# PRD v1"
        assert r["current_version"] == 1

    @pytest.mark.asyncio
    async def test_write_conflito_retorna_payload_estruturado(self):
        ws = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
        await write_spec_document(ws["id"], "prd", "v1", None)
        await write_spec_document(ws["id"], "prd", "v2", 1)
        # expected_version desatualizado
        out = json.loads(await write_spec_document(ws["id"], "prd", "v-conflito", 1))
        assert out["conflict"] is True
        assert out["expected_version"] == 1
        assert out["current_version"] == 2
        assert out["current_content"] == "v2"

    @pytest.mark.asyncio
    async def test_read_documento_inexistente(self):
        ws = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
        out = json.loads(await read_spec_document(ws["id"], "techspec"))
        assert out["found"] is False

    @pytest.mark.asyncio
    async def test_write_em_workspace_inexistente_retorna_error(self):
        import uuid

        out = await write_spec_document(str(uuid.uuid4()), "prd", "x", None)
        assert out.startswith("Error:")


class TestNeverRaise:
    @pytest.mark.asyncio
    async def test_document_type_invalido_vira_string_error(self):
        ws = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
        out = await write_spec_document(ws["id"], "tipo_invalido", "x", None)
        assert out.startswith("Error:")

    @pytest.mark.asyncio
    async def test_workspace_id_malformado_vira_string_error(self):
        out = await read_spec_document("nao-e-uuid", "prd")
        assert out.startswith("Error:")


class TestSearchTool:
    @pytest.mark.asyncio
    async def test_search_sem_specs_retorna_lista_vazia(self, monkeypatch):
        import app.utils.spec_search as spec_search

        # backend indisponível -> search_specs retorna [] (nunca erro)
        monkeypatch.setattr(spec_search, "get_memory_client_safe", lambda: None)
        out = json.loads(await search_specs("qualquer coisa"))
        assert out == {"results": []}
