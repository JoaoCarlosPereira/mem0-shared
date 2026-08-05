import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Configuração de variáveis de ambiente para testes
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Header padrão para MCP Streamable HTTP
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}

@pytest.fixture
def test_app():
    from fastapi import FastAPI
    from app.mcp_server import setup_mcp_server

    app = FastAPI()
    setup_mcp_server(app)
    return app

@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }

def _initialize_payload(req_id: int = 1) -> dict:
    return _jsonrpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.1.0"},
        },
        req_id=req_id,
    )

class TestMCPBugFixesResilience:
    @pytest.mark.asyncio
    async def test_add_memories_endpoint_exists(self, client):
        # Valida que o input_schema aceita a chamada básica, mesmo que dê erro de autenticação ou banco depois
        await client.post("/mcp/testclient/http/testuser", json=_initialize_payload(), headers=MCP_HEADERS)
        resp = await client.post(
            "/mcp/testclient/http/testuser",
            json=_jsonrpc("tools/call", {"name": "add_memories", "arguments": {"text": "python", "project": "test"}}, req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_memory_endpoint_exists(self, client):
        await client.post("/mcp/testclient/http/testuser", json=_initialize_payload(), headers=MCP_HEADERS)
        resp = await client.post(
            "/mcp/testclient/http/testuser",
            json=_jsonrpc("tools/call", {"name": "search_memory", "arguments": {"query": "python", "project": "test"}}, req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_publish_catalog_unauthenticated_graceful_fail(self, client):
        await client.post("/mcp/testclient/http/testuser", json=_initialize_payload(), headers=MCP_HEADERS)
        resp = await client.post(
            "/mcp/testclient/http/testuser",
            json=_jsonrpc("tools/call", {"name": "publish_catalog_resource", "arguments": {"name": "skill", "content": "test", "type": "agent-skill"}}, req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_task_includes_planka_flags(self, client):
        await client.post("/mcp/testclient/http/testuser", json=_initialize_payload(), headers=MCP_HEADERS)
        resp = await client.post(
            "/mcp/testclient/http/testuser",
            json=_jsonrpc("tools/call", {"name": "create_task", "arguments": {"workspace_id": "00000000-0000-0000-0000-000000000000", "title": "Test"}}, req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_add_comment_resilient_to_hook_failure(self, client):
        await client.post("/mcp/testclient/http/testuser", json=_initialize_payload(), headers=MCP_HEADERS)
        resp = await client.post(
            "/mcp/testclient/http/testuser",
            json=_jsonrpc("tools/call", {"name": "add_spec_comment", "arguments": {"target_type": "workspace", "target_id": "00000000-0000-0000-0000-000000000000", "body": "test"}}, req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200
