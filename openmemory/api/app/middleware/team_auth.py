"""Autenticação unificada na borda (ADR-006 da feature auth Google).

Evolução do ``TeamAuthMiddleware`` (task_11/ADR-006 de prontidão-produção) para
um ponto único que resolve QUATRO métodos de credencial:

- ``agent_token`` — token opaco do agente MCP, via ``?token=`` na URL (ADR-003)
  ou header com prefixo ``omtk_``; hash validado em ``agent_tokens`` (cache
  Redis). Credencial explícita inválida/revogada ⇒ 401 em qualquer modo.
- ``session``     — JWT de sessão da UI (``Authorization: Bearer``, formato
  JWT). Inválido/expirado ⇒ 401 em qualquer modo.
- ``team``        — tokens de equipe existentes (``X-API-Key``/Bearer opaco).
  Comportamento 100% preservado nos modos ``off|warn|enforce``.
- ``legacy``      — sem credencial: passa em ``warn`` (default) e é rejeitado
  apenas em ``enforce`` — o fluxo por hostname continua intacto (Fase 1).

A identidade resolvida vai para contextvars (``auth_method_var``,
``auth_user_var``, ``machine_var`` — ``app.utils.logging_context``) para
consumo por auditoria, métricas e MCP. O valor de ``?token=`` nunca aparece em
log (``TokenMaskingFilter`` + logs deste módulo usam só o path).

Modos (env ``AUTH_MODE``): ``off`` (bypass), ``warn`` (default), ``enforce``.
Tokens de equipe: secret ``AUTH_TOKENS_FILE`` ou env ``AUTH_TOKENS``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.agent_tokens import AGENT_TOKEN_PREFIX, resolve_agent_token
from app.utils.logging_context import (
    auth_method_var,
    auth_user_var,
    machine_var,
    team_var,
)
from app.utils.metrics import AUTH_DENIED_TOTAL, AUTH_OK_TOTAL
from app.utils.session_jwt import SessionJwtError, decode_session_jwt

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("/health", "/metrics", "/docs", "/openapi", "/redoc")

# Hostname posicional das rotas MCP: /mcp/{client}/(sse|http)/{hostname}
_MCP_HOST_RE = re.compile(r"^/mcp/[^/]+/(?:sse|http)/([^/?]+)")


@dataclass
class AuthContext:
    """Identidade resolvida para a requisição corrente."""

    method: str  # "session" | "agent_token" | "team" | "legacy"
    user_id: Optional[str] = None
    machine_hostname: Optional[str] = None
    team: Optional[str] = None


def load_team_tokens() -> Dict[str, str]:
    """Carrega o mapa ``token -> team`` de um secret (arquivo) ou env.

    Prioridade: ``AUTH_TOKENS_FILE`` (JSON ``{team: token}`` ou linhas
    ``team:token``) > ``AUTH_TOKENS`` (``team1:tok1,team2:tok2``) > vazio.
    """
    path = os.getenv("AUTH_TOKENS_FILE")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            raw = fh.read().strip()
        try:
            data = json.loads(raw)
            return {tok: team for team, tok in data.items()}
        except json.JSONDecodeError:
            return _parse_pairs(raw.replace("\n", ","))
    inline = os.getenv("AUTH_TOKENS")
    if inline:
        return _parse_pairs(inline)
    return {}


def _parse_pairs(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for pair in text.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        team, tok = pair.split(":", 1)
        out[tok.strip()] = team.strip()
    return out


def _extract_token(request: Request) -> Optional[str]:
    key = request.headers.get("x-api-key")
    if key:
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


def _mcp_hostname(path: str) -> Optional[str]:
    match = _MCP_HOST_RE.match(path)
    return match.group(1) if match else None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        mode: Optional[str] = None,
        token_to_team: Optional[Dict[str, str]] = None,
    ):
        super().__init__(app)
        self._mode = (mode or os.getenv("AUTH_MODE", "warn")).strip().lower()
        self._tokens = token_to_team if token_to_team is not None else load_team_tokens()

    async def dispatch(self, request: Request, call_next):
        if self._mode == "off" or any(
            request.url.path.startswith(p) for p in _SKIP_PREFIXES
        ):
            return await call_next(request)

        path = request.url.path

        # 1) ?token= nas rotas MCP — credencial explícita de agente (ADR-003).
        query_token = (
            request.query_params.get("token") if path.startswith("/mcp") else None
        )
        if query_token:
            return await self._handle_agent_token(request, call_next, query_token)

        header_token = _extract_token(request)
        if header_token:
            # 2) JWT de sessão da UI — credencial explícita de pessoa.
            if _looks_like_jwt(header_token):
                try:
                    claims = decode_session_jwt(header_token)
                except SessionJwtError:
                    AUTH_DENIED_TOTAL.labels(mode=self._mode).inc()
                    return self._unauthorized(request, "sessão inválida ou expirada")
                AUTH_OK_TOTAL.labels(method="session").inc()
                ctx = AuthContext(method="session", user_id=str(claims.get("sub") or ""))
                return await self._call_with_context(request, call_next, ctx)

            # 3) Token de agente enviado por header (prefixo identificável).
            if header_token.startswith(AGENT_TOKEN_PREFIX):
                return await self._handle_agent_token(request, call_next, header_token)

            # 4) Token de equipe (comportamento original preservado).
            team = self._tokens.get(header_token)
            if team is not None:
                AUTH_OK_TOTAL.labels(method="team").inc()
                ctx = AuthContext(method="team", team=team)
                return await self._call_with_context(request, call_next, ctx)

        # 5) Sem credencial válida — caminho legado (idêntico ao anterior).
        AUTH_DENIED_TOTAL.labels(mode=self._mode).inc()
        if self._mode == "enforce":
            return self._unauthorized(request, "invalid or missing team token")
        logger.warning(
            "auth warn: requisição sem token de equipe válido em %s", path
        )
        ctx = AuthContext(method="legacy", machine_hostname=_mcp_hostname(path))
        return await self._call_with_context(request, call_next, ctx)

    async def _handle_agent_token(self, request: Request, call_next, raw_token: str):
        """Valida token de agente; explícito e inválido ⇒ 401 em qualquer modo."""
        user_id = resolve_agent_token(raw_token)
        if user_id is None:
            AUTH_DENIED_TOTAL.labels(mode=self._mode).inc()
            return self._unauthorized(
                request, "token de agente inválido ou revogado"
            )
        AUTH_OK_TOTAL.labels(method="agent_token").inc()
        ctx = AuthContext(
            method="agent_token",
            user_id=user_id,
            machine_hostname=_mcp_hostname(request.url.path),
        )
        return await self._call_with_context(request, call_next, ctx)

    async def _call_with_context(self, request: Request, call_next, ctx: AuthContext):
        """Popula as contextvars de identidade com reset garantido no finally."""
        tokens = [
            (auth_method_var, auth_method_var.set(ctx.method)),
            (auth_user_var, auth_user_var.set(ctx.user_id or "")),
            (machine_var, machine_var.set(ctx.machine_hostname or "")),
        ]
        if ctx.team:
            tokens.append((team_var, team_var.set(ctx.team)))
        try:
            return await call_next(request)
        finally:
            for var, token in reversed(tokens):
                var.reset(token)

    def _unauthorized(self, request: Request, detail: str) -> JSONResponse:
        """401 com headers CORS ecoados — o middleware roda fora do CORSMiddleware."""
        response = JSONResponse(status_code=401, content={"detail": detail})
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response


# Alias de compatibilidade: consumidores existentes (main.py, testes) continuam
# importando ``TeamAuthMiddleware``.
TeamAuthMiddleware = AuthMiddleware
