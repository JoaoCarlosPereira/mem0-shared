"""Regression: invalid Bearer in AUTH_MODE=warn must 401; Bearer local is legacy."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.team_auth import AuthMiddleware
from app.utils.logging_context import auth_method_var

TOKENS = {"tok-alpha": "alpha"}


def _app(mode: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, mode=mode, token_to_team=TOKENS)

    @app.get("/whoami")
    def whoami():
        return {"method": auth_method_var.get() or None}

    return app


def test_bearer_local_is_legacy_in_warn():
    with TestClient(_app("warn")) as client:
        body = client.get("/whoami", headers={"authorization": "Bearer local"}).json()
    assert body["method"] == "legacy"


def test_bearer_local_rejected_in_enforce():
    with TestClient(_app("enforce")) as client:
        resp = client.get("/whoami", headers={"authorization": "Bearer local"})
    assert resp.status_code == 401


def test_invalid_opaque_bearer_rejected_in_warn():
    with TestClient(_app("warn")) as client:
        resp = client.get("/whoami", headers={"authorization": "Bearer garbage-token"})
    assert resp.status_code == 401


def test_absent_header_is_legacy_in_warn():
    with TestClient(_app("warn")) as client:
        body = client.get("/whoami").json()
    assert body["method"] == "legacy"
