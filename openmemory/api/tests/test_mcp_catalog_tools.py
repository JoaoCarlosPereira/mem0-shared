import json
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import mcp_server
from app.utils.agentregistry import AgentRegistryResourceNotFound

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _skill_resource(name="team-skill", tag="v1"):
    return {
        "apiVersion": "ar.dev/v1alpha1",
        "kind": "Skill",
        "metadata": {
            "namespace": "default",
            "name": name,
            "tag": tag,
            "labels": {"team": "platform"},
        },
        "spec": {
            "title": "Team Skill",
            "description": "Reusable team skill",
            "source": {"repository": {"url": "https://example.invalid/repo.git"}},
        },
    }


class FakeCatalogClient:
    def __init__(self):
        self.calls = []
        self.items = [_skill_resource("team-skill"), _skill_resource("other-skill")]
        self.get_error = None

    async def list_resources(self, **kwargs):
        self.calls.append(("list", kwargs))
        return {"items": self.items, "nextCursor": ""}

    async def get_resource(self, **kwargs):
        self.calls.append(("get", kwargs))
        if self.get_error:
            raise self.get_error
        return _skill_resource(kwargs["name"], kwargs.get("tag") or "latest")

    async def apply_resource(self, **kwargs):
        self.calls.append(("apply", kwargs))
        return {
            "results": [
                {
                    "apiVersion": kwargs["resource"].get("apiVersion"),
                    "kind": kwargs["resource"].get("kind"),
                    "name": kwargs["resource"]["metadata"]["name"],
                    "status": "created",
                }
            ]
        }


class FakeRecipeService:
    def __init__(self):
        self.calls = []

    async def build(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "version": "1",
            "resource_kind": kwargs["kind"],
            "name": kwargs["name"],
            "tag": kwargs["tag"],
            "target": kwargs["target"],
            "user_id": kwargs["user_id"],
            "resource": {},
            "source": {"type": "registry"},
            "steps": [{"id": "verify-target", "type": "verify"}],
            "rollback": [],
        }


@pytest.mark.asyncio
async def test_search_catalog_accepts_empty_query_and_honors_limit(monkeypatch):
    fake = FakeCatalogClient()
    monkeypatch.setattr(mcp_server, "get_agent_registry_client", lambda: fake)

    out = await mcp_server.search_catalog(query="", kind="skill", limit=1)
    body = json.loads(out)

    assert len(body["results"]) == 1
    assert body["results"][0]["name"] == "team-skill"
    assert fake.calls[0][1]["limit"] == 1


@pytest.mark.asyncio
async def test_get_catalog_resource_returns_error_on_missing_resource(monkeypatch):
    fake = FakeCatalogClient()
    fake.get_error = AgentRegistryResourceNotFound()
    monkeypatch.setattr(mcp_server, "get_agent_registry_client", lambda: fake)

    out = await mcp_server.get_catalog_resource(kind="skill", name="missing", tag="v1")

    assert out == "Error: recurso não encontrado no AgentRegistry"


@pytest.mark.asyncio
async def test_publish_catalog_resource_forwards_apply_payload_and_auth(monkeypatch):
    fake = FakeCatalogClient()
    monkeypatch.setattr(mcp_server, "get_agent_registry_client", lambda: fake)
    token = mcp_server.registry_auth_headers_var.set({"Authorization": "Bearer omtk_token"})
    try:
        out = await mcp_server.publish_catalog_resource(
            resource=_skill_resource("published-skill"),
            dry_run=True,
            confirm_user_requested=True,
        )
    finally:
        mcp_server.registry_auth_headers_var.reset(token)

    body = json.loads(out)
    assert body["result"]["results"][0]["status"] == "created"
    call = fake.calls[0][1]
    assert call["resource"]["metadata"]["name"] == "published-skill"
    assert call["dry_run"] is True
    assert call["auth_headers"] == {"Authorization": "Bearer omtk_token"}


@pytest.mark.asyncio
async def test_publish_catalog_resource_synthesizes_legacy_auth_when_absent(monkeypatch):
    """Hostname-only MCP (same as memories) must still authenticate to the loja."""
    fake = FakeCatalogClient()
    monkeypatch.setattr(mcp_server, "get_agent_registry_client", lambda: fake)
    monkeypatch.setenv("MEM0_AUTH_ALLOW_LEGACY", "1")
    method = mcp_server.auth_method_var.set("legacy")
    try:
        out = await mcp_server.publish_catalog_resource(
            resource=_skill_resource("legacy-skill"),
            dry_run=True,
            confirm_user_requested=True,
        )
    finally:
        mcp_server.auth_method_var.reset(method)

    body = json.loads(out)
    assert body["result"]["results"][0]["status"] == "created"
    assert fake.calls[0][1]["auth_headers"] == {"Authorization": "Bearer local"}


@pytest.mark.asyncio
async def test_get_install_recipe_delegates_to_service_with_mcp_actor_and_auth(monkeypatch):
    service = FakeRecipeService()
    monkeypatch.setattr(mcp_server, "get_catalog_install_recipe_service", lambda: service)
    token_auth = mcp_server.registry_auth_headers_var.set({"Authorization": "Bearer omtk_token"})
    token_method = mcp_server.auth_method_var.set("agent_token")
    token_user = mcp_server.auth_user_var.set("person-1")
    try:
        out = await mcp_server.get_install_recipe(
            kind="skill",
            name="team-skill",
            tag="v1",
            target="cursor",
            confirm_user_requested=True,
        )
    finally:
        mcp_server.auth_user_var.reset(token_user)
        mcp_server.auth_method_var.reset(token_method)
        mcp_server.registry_auth_headers_var.reset(token_auth)

    body = json.loads(out)
    assert body["recipe"]["target"] == "cursor"
    assert service.calls == [
        {
            "kind": "skill",
            "name": "team-skill",
            "tag": "v1",
            "target": "cursor",
            "user_id": "person-1",
            "auth_headers": {"Authorization": "Bearer omtk_token"},
        }
    ]


@pytest.mark.asyncio
async def test_authenticated_mcp_tool_call_forwards_authorization_header(monkeypatch):
    fake = FakeCatalogClient()
    monkeypatch.setattr(mcp_server, "get_agent_registry_client", lambda: fake)

    app = FastAPI()
    mcp_server.setup_mcp_server(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/mcp/cursor/http/Mini-PC",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            },
            headers={**MCP_HEADERS, "Authorization": "Bearer omtk_token"},
        )
        response = await client.post(
            "/mcp/cursor/http/Mini-PC",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search_catalog",
                    "arguments": {"query": "team", "kind": "skill", "limit": 5},
                },
            },
            headers={**MCP_HEADERS, "Authorization": "Bearer omtk_token"},
        )

    assert response.status_code == 200
    payload = response.json()
    result_text = payload["result"]["structuredContent"]["result"]
    body = json.loads(result_text)
    assert body["results"][0]["name"] == "team-skill"
    assert fake.calls[-1][1]["auth_headers"] == {"Authorization": "Bearer omtk_token"}
