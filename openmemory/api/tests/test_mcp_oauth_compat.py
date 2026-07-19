"""Testes do shim OAuth para MCP HTTP legado (hostname-only)."""

import importlib.util
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "mcp_oauth_compat.py"
_spec = importlib.util.spec_from_file_location("mcp_oauth_compat_under_test", _PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
router = _mod.router


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://memhost:8765") as ac:
        yield ac


class TestLegacyOAuthShim:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["off", "warn"])
    async def test_metadata_e_token_em_modo_legado(self, client, monkeypatch, mode):
        monkeypatch.setenv("AUTH_MODE", mode)
        meta = await client.get("/.well-known/oauth-authorization-server")
        assert meta.status_code == 200
        body = meta.json()
        assert body["token_endpoint"] == "http://memhost:8765/token"
        assert "client_credentials" in body["grant_types_supported"]

        tok = await client.post("/token", data={"grant_type": "client_credentials"})
        assert tok.status_code == 200
        assert tok.json()["access_token"] == "local"
        assert tok.json()["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_enforce_retorna_404_sem_json(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "enforce")
        meta = await client.get("/.well-known/oauth-authorization-server")
        assert meta.status_code == 404
        assert meta.text == ""

        tok = await client.post("/token")
        assert tok.status_code == 404
        assert tok.text == ""
