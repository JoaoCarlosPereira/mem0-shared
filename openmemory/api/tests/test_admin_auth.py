"""Tests for admin mutation auth (require_admin) and related guards."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.middleware.team_auth import AuthMiddleware
from app.utils.admin_auth import require_admin
from app.utils.session_jwt import issue_session_jwt

SECRET = "segredo-de-teste-com-32-bytes-ok!"
ADMIN = "super-secret-admin-token"


def _app():
    app = FastAPI()
    app.add_middleware(AuthMiddleware, mode="warn", token_to_team={"tok-alpha": "alpha"})

    @app.post("/admin/backup/restore")
    def restore(_: None = Depends(require_admin)):
        return {"ok": True}

    return app


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN)
    monkeypatch.delenv("AUTH_ADMIN_EMAILS", raising=False)


def test_restore_denied_without_credentials():
    with TestClient(_app()) as client:
        resp = client.post("/admin/backup/restore")
    assert resp.status_code == 401


def test_restore_denied_for_legacy_bearer_local():
    with TestClient(_app()) as client:
        resp = client.post(
            "/admin/backup/restore",
            headers={"authorization": "Bearer local"},
        )
    assert resp.status_code == 401


def test_restore_allowed_with_admin_token_header():
    with TestClient(_app()) as client:
        resp = client.post(
            "/admin/backup/restore",
            headers={"x-admin-token": ADMIN},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_restore_allowed_with_session_jwt(monkeypatch):
    monkeypatch.delenv("AUTH_ADMIN_EMAILS", raising=False)
    token = issue_session_jwt(user_id="u1", email="ops@corp.com")
    with TestClient(_app()) as client:
        resp = client.post(
            "/admin/backup/restore",
            headers={"authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200


def test_restore_denied_when_email_not_in_allowlist(monkeypatch):
    monkeypatch.setenv("AUTH_ADMIN_EMAILS", "admin@corp.com")
    token = issue_session_jwt(user_id="u1", email="ops@corp.com")
    with TestClient(_app()) as client:
        resp = client.post(
            "/admin/backup/restore",
            headers={"authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 403


def test_restore_allowed_when_email_in_allowlist(monkeypatch):
    monkeypatch.setenv("AUTH_ADMIN_EMAILS", "admin@corp.com,ops@corp.com")
    token = issue_session_jwt(user_id="u1", email="ops@corp.com")
    with TestClient(_app()) as client:
        resp = client.post(
            "/admin/backup/restore",
            headers={"authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
