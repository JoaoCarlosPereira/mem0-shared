"""Registry auth synthesis — loja must accept the same principals as Mem0 memories."""

from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import jwt
import pytest

from app.utils import agentregistry
from app.utils.logging_context import auth_email_var, auth_method_var, auth_user_var


SECRET = "unit-test-registry-auth-secret-32b!!"


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("MEM0_AUTH_ALLOW_LEGACY", "1")
    monkeypatch.setenv("AUTH_MODE", "warn")


def test_legacy_session_synthesizes_bearer_local():
    method = auth_method_var.set("legacy")
    try:
        headers = agentregistry.synthesize_registry_auth_headers()
    finally:
        auth_method_var.reset(method)
    assert headers == {"Authorization": "Bearer local"}


def test_empty_method_synthesizes_bearer_local_when_legacy_allowed():
    method = auth_method_var.set("")
    try:
        headers = agentregistry.synthesize_registry_auth_headers()
    finally:
        auth_method_var.reset(method)
    assert headers == {"Authorization": "Bearer local"}


def test_session_method_reissues_jwt():
    method = auth_method_var.set("session")
    user = auth_user_var.set("person-42")
    email = auth_email_var.set("dev@sysmo.com.br")
    try:
        headers = agentregistry.synthesize_registry_auth_headers()
    finally:
        auth_email_var.reset(email)
        auth_user_var.reset(user)
        auth_method_var.reset(method)

    assert headers and headers["Authorization"].startswith("Bearer ")
    raw = headers["Authorization"].split(" ", 1)[1]
    claims = jwt.decode(raw, SECRET, algorithms=["HS256"])
    assert claims["sub"] == "person-42"
    assert claims["email"] == "dev@sysmo.com.br"


def test_agent_token_method_reissues_jwt_for_registry():
    method = auth_method_var.set("agent_token")
    user = auth_user_var.set("person-omtk")
    try:
        headers = agentregistry.synthesize_registry_auth_headers()
    finally:
        auth_user_var.reset(user)
        auth_method_var.reset(method)

    raw = headers["Authorization"].split(" ", 1)[1]
    claims = jwt.decode(raw, SECRET, algorithms=["HS256"])
    assert claims["sub"] == "person-omtk"


def test_resolve_prefers_explicit_headers():
    out = agentregistry.resolve_registry_auth_headers(
        {"Authorization": "Bearer omtk_keep"}
    )
    assert out == {"Authorization": "Bearer omtk_keep"}


def test_legacy_blocked_when_enforce_and_flag_off(monkeypatch):
    monkeypatch.setenv("MEM0_AUTH_ALLOW_LEGACY", "0")
    monkeypatch.setenv("AUTH_MODE", "enforce")
    method = auth_method_var.set("legacy")
    try:
        assert agentregistry.synthesize_registry_auth_headers() is None
    finally:
        auth_method_var.reset(method)


def test_auth_headers_from_http_request_token_query():
    class _Req:
        headers = {}
        query_params = {"token": "omtk_abc"}

    assert agentregistry.auth_headers_from_http_request(_Req()) == {
        "Authorization": "Bearer omtk_abc"
    }
