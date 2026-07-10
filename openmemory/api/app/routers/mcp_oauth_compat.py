"""Shim OAuth para clientes MCP HTTP em modo legado (hostname-only).

Clientes recentes (Cursor, Claude Code) com transporte HTTP e URL sem credencial
disparam descoberta OAuth (``/.well-known/oauth-authorization-server``). O
FastAPI devolve 404 com ``{"detail":"Not Found"}``, o SDK tenta parsear como
resposta OAuth e falha — embora o ``AuthMiddleware`` já aceite o fluxo legado
(``AUTH_MODE=off|warn``).

Quando o shim está ativo (``AUTH_MODE`` em ``off`` ou ``warn``), expomos metadados
mínimos e ``POST /token`` com ``client_credentials`` que devolve o bearer fixo
``local`` (o mesmo de ``MEM0_API_KEY=local`` na receita de provisionamento). O
middleware trata ``Authorization: Bearer local`` como caminho legado.

Em ``AUTH_MODE=enforce`` as rotas respondem 404 sem corpo JSON para não induzir
o cliente a um fluxo OAuth inválido.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(tags=["mcp-oauth-compat"])

# Alinhado a provision.env MEM0_API_KEY quando não há token de agente.
LEGACY_MCP_BEARER = "local"


def legacy_oauth_shim_enabled() -> bool:
    mode = (os.getenv("AUTH_MODE", "warn") or "warn").strip().lower()
    return mode in ("off", "warn")


def _oauth_disabled() -> Response:
    return Response(status_code=404)


def _request_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata(request: Request):
    """RFC 8414 — metadados mínimos para client_credentials estático."""
    if not legacy_oauth_shim_enabled():
        return _oauth_disabled()
    base = _request_base(request)
    return {
        "issuer": base,
        "token_endpoint": f"{base}/token",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


@router.post("/token")
async def legacy_oauth_token(request: Request):
    """Emite o bearer fixo ``local`` para clientes que exigem fluxo OAuth."""
    if not legacy_oauth_shim_enabled():
        return _oauth_disabled()
    # Form ou JSON — clientes MCP variam; ignoramos o corpo no modo legado.
    return JSONResponse(
        {
            "access_token": LEGACY_MCP_BEARER,
            "token_type": "bearer",
            "expires_in": 86400,
        }
    )
