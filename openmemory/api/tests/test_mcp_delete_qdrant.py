"""MCP delete_memories must remove Qdrant points even when SQL catalog has no row."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ["MEM0_ALLOW_MEMORY_DELETE"] = "1"
os.environ["MEM0_ALLOW_BULK_DELETE"] = "1"

from app import mcp_server
from app.mcp_server import delete_memories


@pytest.fixture
def patched_delete_client():
    client = MagicMock()
    client.vector_store.collection_name = "openmemory"
    client.vector_store.client.retrieve.return_value = [SimpleNamespace(id="68e16c32-bcb5-4857-bd2e-9d2b5aba48c9")]
    with (
        patch.object(mcp_server, "get_memory_client_safe", return_value=client),
        patch.object(mcp_server, "bind_active_collection"),
        patch.object(mcp_server, "resolve_hostname", return_value="S0258"),
        patch.object(mcp_server, "get_user_and_app") as gua,
        patch.object(mcp_server, "SessionLocal") as session_local,
    ):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        session_local.return_value = db
        gua.return_value = (MagicMock(id="user"), MagicMock(id="app"))
        mcp_server.user_id_var.set("S0258")
        mcp_server.client_name_var.set("cursor")
        yield client, db


@pytest.mark.asyncio
async def test_delete_removes_qdrant_point_without_sql_row(patched_delete_client):
    client, _db = patched_delete_client
    out = await delete_memories(["68e16c32-bcb5-4857-bd2e-9d2b5aba48c9"])
    assert "Successfully deleted 1" in out
    client.delete.assert_called_once_with("68e16c32-bcb5-4857-bd2e-9d2b5aba48c9")


@pytest.mark.asyncio
async def test_delete_reports_missing_ids(patched_delete_client):
    client, _db = patched_delete_client
    client.vector_store.client.retrieve.return_value = []
    out = await delete_memories(["00000000-0000-0000-0000-000000000001"])
    assert "No accessible memories found" in out
    client.delete.assert_not_called()
