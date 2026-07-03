"""Testes do token de agente imutável (ADR-008).

Get-or-create idempotente: uma conta tem UM token, criado na primeira chamada,
devolvido igual nas seguintes (inclusive o valor em claro — exibição
permanente). Sem rotação nem DELETE via API; ``revoked_at`` administrativo
continua bloqueando no middleware (coberto em test_auth_middleware/E2E).
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database_module
from app.database import Base, get_db
from app.middleware.team_auth import AuthMiddleware
from app.models import USER_TYPE_PERSON, AgentToken, User
from app.routers import agent_tokens as agent_tokens_module
from app.utils.agent_tokens import AGENT_TOKEN_PREFIX, hash_token
from app.utils.logging_context import auth_method_var
from app.utils.session_jwt import issue_session_jwt

SECRET = "segredo-de-teste-com-32-bytes-ok!"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.delenv("REDIS_URL", raising=False)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database_module, "SessionLocal", Session)
    yield Session
    engine.dispose()


def _make_app(Session, *, with_middleware: bool = False) -> FastAPI:
    app = FastAPI()
    if with_middleware:
        app.add_middleware(AuthMiddleware, mode="warn", token_to_team={})
    app.include_router(agent_tokens_module.router)

    @app.post("/mcp/claude-code/http/{host}")
    def mcp(host: str):
        return {"method": auth_method_var.get() or None}

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    return app


def _person_and_bearer(Session):
    db = Session()
    try:
        user = User(user_id="sub-1", user_type=USER_TYPE_PERSON, google_sub="sub-1")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, {
            "Authorization": f"Bearer {issue_session_jwt(user_id=user.id)}"
        }
    finally:
        db.close()


class TestImmutableToken:
    def test_primeira_chamada_cria_com_valor_em_claro(self, env):
        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env))

        resp = client.post("/api/v1/agent-token", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["token"].startswith(AGENT_TOKEN_PREFIX)
        assert body["token"].startswith(body["prefix"])

        db = env()
        try:
            row = db.query(AgentToken).one()
            assert row.token_value == body["token"]
            assert row.token_hash == hash_token(body["token"])
        finally:
            db.close()

    def test_post_repetido_devolve_o_mesmo_token_sem_rotacionar(self, env):
        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env))

        first = client.post("/api/v1/agent-token", headers=headers).json()
        second = client.post("/api/v1/agent-token", headers=headers).json()
        assert second["token"] == first["token"], "token é imutável (ADR-008)"

        db = env()
        try:
            assert db.query(AgentToken).count() == 1
        finally:
            db.close()

    def test_get_devolve_valor_permanentemente(self, env):
        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env))

        created = client.post("/api/v1/agent-token", headers=headers).json()
        for _ in range(2):  # exibição eterna: toda consulta traz o valor
            meta = client.get("/api/v1/agent-token", headers=headers).json()
            assert meta["token"] == created["token"]

    def test_get_sem_token_404(self, env):
        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env))
        assert client.get("/api/v1/agent-token", headers=headers).status_code == 404

    def test_delete_nao_existe_mais(self, env):
        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env))
        client.post("/api/v1/agent-token", headers=headers)
        assert client.delete("/api/v1/agent-token", headers=headers).status_code == 405

    def test_sem_sessao_401(self, env):
        client = TestClient(_make_app(env))
        assert client.post("/api/v1/agent-token").status_code == 401


class TestMethodEnforcement:
    def test_credencial_agent_token_recebe_403(self, env):
        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env, with_middleware=True))
        raw = client.post("/api/v1/agent-token", headers=headers).json()["token"]

        resp = client.post(
            "/api/v1/agent-token",
            headers={**headers, "x-api-key": raw},
        )
        assert resp.status_code == 403


class TestEndToEndWithMiddleware:
    def test_token_imutavel_autentica_e_revogacao_administrativa_bloqueia(self, env):
        from app.models import get_current_utc_time

        _, headers = _person_and_bearer(env)
        client = TestClient(_make_app(env, with_middleware=True))

        raw = client.post("/api/v1/agent-token", headers=headers).json()["token"]
        ok = client.post(f"/mcp/claude-code/http/DESKTOP-01?token={raw}")
        assert ok.status_code == 200
        assert ok.json()["method"] == "agent_token"

        # Válvula de emergência (ADR-008): revogação direta no banco continua
        # sendo honrada pelo middleware.
        db = env()
        try:
            row = db.query(AgentToken).one()
            row.revoked_at = get_current_utc_time()
            db.commit()
        finally:
            db.close()
        denied = client.post(f"/mcp/claude-code/http/DESKTOP-01?token={raw}")
        assert denied.status_code == 401
