"""MCP memory reads must never be blocked by rate limiting."""

import json
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware, RedisSlidingWindowLimiter


class FakeRedis:
    def __init__(self):
        self.z = {}

    def zremrangebyscore(self, k, mn, mx):
        d = self.z.get(k, {})
        self.z[k] = {m: s for m, s in d.items() if not (mn <= s <= mx)}

    def zcard(self, k):
        return len(self.z.get(k, {}))

    def zadd(self, k, mapping):
        self.z.setdefault(k, {}).update(mapping)

    def zrange(self, k, a, b, withscores=False):
        items = sorted(self.z.get(k, {}).items(), key=lambda x: x[1])
        sl = items[a:(b + 1) if b >= 0 else None]
        return [(m, s) for m, s in sl] if withscores else [m for m, _ in sl]

    def expire(self, k, t):
        pass


def _limiter():
    return RedisSlidingWindowLimiter(client=FakeRedis(), clock=lambda: 1000.0)


def _mcp_app(limiter):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.post("/mcp/claude/http/{host}")
    def mcp(host: str):
        return {"ok": True, "host": host}

    @app.post("/api/v1/memories/shared-filter")
    def shared_filter():
        return {"ok": True}

    return app


def _mcp_call(tool: str):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": {"project": "sysmovs", "query": "x"}},
    }


def test_mcp_search_never_rate_limited(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "1")
    monkeypatch.setenv("RL_BURST", "1")
    with TestClient(_mcp_app(_limiter())) as client:
        h = {"Content-Type": "application/json"}
        path = "/mcp/claude/http/S0293"
        for _ in range(25):
            assert client.post(path, headers=h, content=json.dumps(_mcp_call("search_memory"))).status_code == 200


def test_mcp_list_never_rate_limited(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "1")
    monkeypatch.setenv("RL_BURST", "1")
    with TestClient(_mcp_app(_limiter())) as client:
        h = {"Content-Type": "application/json"}
        path = "/mcp/claude/http/S0293"
        for _ in range(25):
            assert client.post(path, headers=h, content=json.dumps(_mcp_call("list_memories"))).status_code == 200


def test_mcp_write_still_rate_limited(monkeypatch):
    monkeypatch.setenv("RL_WRITE_PER_MIN", "2")
    monkeypatch.setenv("RL_BURST", "100")
    with TestClient(_mcp_app(_limiter())) as client:
        h = {"Content-Type": "application/json"}
        path = "/mcp/claude/http/S0293"
        assert client.post(path, headers=h, content=json.dumps(_mcp_call("add_memories"))).status_code == 200
        assert client.post(path, headers=h, content=json.dumps(_mcp_call("add_memories"))).status_code == 200
        assert client.post(path, headers=h, content=json.dumps(_mcp_call("add_memories"))).status_code == 429


def test_shared_filter_never_rate_limited(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "1")
    monkeypatch.setenv("RL_BURST", "1")
    with TestClient(_mcp_app(_limiter())) as client:
        for _ in range(10):
            assert client.post("/api/v1/memories/shared-filter").status_code == 200


def test_mcp_initialize_skips_rate_limit(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "1")
    monkeypatch.setenv("RL_BURST", "1")
    with TestClient(_mcp_app(_limiter())) as client:
        h = {"Content-Type": "application/json"}
        path = "/mcp/claude/http/S0293"
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        for _ in range(5):
            assert client.post(path, headers=h, content=json.dumps(init)).status_code == 200
