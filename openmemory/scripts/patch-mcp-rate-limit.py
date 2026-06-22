#!/usr/bin/env python3
"""Patch rate_limit middleware: MCP read tools use search quota + higher burst."""

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "api" / "app" / "middleware" / "rate_limit.py"

NEW_CONTENT = '''"""Rate limit por (project, hostname) com janela deslizante no Redis (task_10 / ADR-006).

Substitui o limite global do Traefik por limites granulares na borda da API,
conforme §1 da arquitetura: busca 30/min, escrita 60/min, burst 10/10s. Reaproveita
o Redis já presente. Falha do Redis => fail-open (não derruba requisições).
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Callable, Optional, Tuple

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.utils.identity import resolve_hostname

logger = logging.getLogger(__name__)

_SKIP_PREFIXES = ("/health", "/metrics", "/docs", "/openapi", "/redoc")
_MCP_PREFIX = "/mcp/"
_UI_CLIENT = "openmemory-ui"
# POST bodies that only read state (dashboard list/filter) — not MCP writes.
_READ_POST_SUFFIXES = ("/api/v1/memories/shared-filter", "/api/v1/memories/filter")
# MCP tools/call names that only read memory state (ADR-006: use search quota, not write).
_MCP_READ_TOOLS = frozenset(
    {
        "search_memory",
        "list_memories",
        "get_memory",
        "get_memories",
        "search_memories",
        "peek",
        "list_entities",
    }
)
_MCP_WRITE_TOOLS = frozenset(
    {
        "add_memories",
        "add_memory",
        "update_memory",
        "delete_memories",
        "delete_memory",
        "delete_all_memories",
        "delete_entities",
        "remember",
    }
)
# Handshake / discovery — no quota (agents open sessions with several lightweight calls).
_MCP_SKIP_LIMIT_METHODS = frozenset({"initialize", "notifications/initialized", "tools/list", "ping"})


class RedisSlidingWindowLimiter:
    """Janela deslizante via sorted set: membros são timestamps dentro da janela."""

    def __init__(self, redis_url: Optional[str] = None, *, client=None, clock: Callable[[], float] = time.time):
        self._redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self._client = client
        self._clock = clock
        self._disabled = client is None and not self._redis_url

    def _redis(self):
        if self._disabled:
            return None
        if self._client is None:
            try:
                import redis

                self._client = redis.from_url(self._redis_url, decode_responses=True)
                self._client.ping()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis indisponível; rate limit em fail-open: %s", exc)
                self._disabled = True
                return None
        return self._client

    def allow(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Retorna ``(permitido, retry_after_segundos)``. Fail-open em erro/sem Redis."""
        r = self._redis()
        if r is None:
            return True, 0
        now = self._clock()
        zkey = f"rl:{key}"
        try:
            r.zremrangebyscore(zkey, 0, now - window)
            count = r.zcard(zkey)
            if count >= limit:
                oldest = r.zrange(zkey, 0, 0, withscores=True)
                retry = window
                if oldest:
                    retry = int(window - (now - oldest[0][1])) + 1
                return False, max(retry, 1)
            r.zadd(zkey, {f"{now}:{uuid.uuid4().hex}": now})
            r.expire(zkey, window)
            return True, 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate limit erro (fail-open): %s", exc)
            return True, 0


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _restore_request_body(request: Request, body: bytes) -> None:
    """Allow downstream handlers to read the POST body after middleware inspection."""

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # noqa: SLF001


def _mcp_rpc_category(body: bytes) -> Optional[str]:
    """Classify MCP JSON-RPC POST as ``search``, ``write``, or ``skip`` (None)."""
    if not body:
        return "search"
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "search"
    method = payload.get("method")
    if method in _MCP_SKIP_LIMIT_METHODS:
        return None
    if method != "tools/call":
        return "search"
    tool = (payload.get("params") or {}).get("name")
    if tool in _MCP_READ_TOOLS:
        return "search"
    if tool in _MCP_WRITE_TOOLS:
        return "write"
    return "search"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Aplica limites por (project, hostname) + burst por hostname."""

    def __init__(self, app, *, limiter: Optional[RedisSlidingWindowLimiter] = None):
        super().__init__(app)
        self._limiter = limiter or RedisSlidingWindowLimiter()
        self._search_per_min = _env_int("RL_SEARCH_PER_MIN", 30)
        self._write_per_min = _env_int("RL_WRITE_PER_MIN", 60)
        self._burst = _env_int("RL_BURST", 10)
        self._mcp_burst = _env_int("RL_MCP_BURST", 40)
        self._burst_window = _env_int("RL_BURST_WINDOW", 10)

    @staticmethod
    def _scope(request: Request) -> Tuple[str, str]:
        client_name = request.headers.get("x-client-name", "").strip()
        if client_name == _UI_CLIENT:
            return "default", f"ui:{client_name}"

        hostname = request.headers.get("x-hostname")
        if not hostname:
            parts = [p for p in request.url.path.split("/") if p]
            # /mcp/{client}/sse/{user_id} -> user_id carrega o hostname (ADR-003)
            hostname = parts[-1] if "mcp" in parts else None
        hostname = resolve_hostname(hostname)
        project = request.headers.get("x-project") or request.query_params.get("project") or "default"
        return project, hostname

    def _limit_for(self, request: Request, *, mcp_category: Optional[str] = None) -> Optional[Tuple[str, int]]:
        path = request.url.path.rstrip("/") or "/"
        if mcp_category is None and path.startswith(_MCP_PREFIX):
            return None
        if request.method in ("GET", "HEAD"):
            return "search", self._search_per_min
        if mcp_category == "search" or any(path.endswith(suffix) for suffix in _READ_POST_SUFFIXES):
            return "search", self._search_per_min
        if mcp_category == "write":
            return "write", self._write_per_min
        return "write", self._write_per_min

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        mcp_category: Optional[str] = None
        if path.startswith(_MCP_PREFIX) and request.method == "POST":
            body = await request.body()
            _restore_request_body(request, body)
            mcp_category = _mcp_rpc_category(body)
            if mcp_category is None:
                return await call_next(request)

        project, hostname = self._scope(request)
        limit_pair = self._limit_for(request, mcp_category=mcp_category)
        if limit_pair is None:
            return await call_next(request)
        category, limit = limit_pair

        # Burst por hostname (protege contra rajadas independentemente do project).
        if hostname.startswith("ui:"):
            burst_limit = _env_int("RL_UI_BURST", 120)
            burst_key = f"burst:{hostname}"
        elif path.startswith(_MCP_PREFIX) and category == "search":
            burst_limit = self._mcp_burst
            burst_key = f"burst:mcp:{hostname}"
        else:
            burst_limit = self._burst
            burst_key = f"burst:{hostname}"
        ok_burst, retry_b = self._limiter.allow(burst_key, burst_limit, self._burst_window)
        if not ok_burst:
            return _too_many(retry_b)

        ok, retry = self._limiter.allow(f"{category}:{project}:{hostname}", limit, 60)
        if not ok:
            return _too_many(retry)
        return await call_next(request)


def _too_many(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "rate limit exceeded"},
        headers={"Retry-After": str(retry_after)},
    )
'''


def main() -> None:
    TARGET.write_text(NEW_CONTENT, encoding="utf-8")
    print(f"Patched {TARGET}")


if __name__ == "__main__":
    main()
