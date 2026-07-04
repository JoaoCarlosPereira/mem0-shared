"""Testes da task_11 (feature auth Google): integração MCP com identidade.

Cobre a atribuição de pessoa quando o agente autentica por token
(``_usage_user_id``), o log de divergência máquina-do-token × hostname-da-URL
e o fluxo E2E backend: login → onboarding → geração de token → provision →
requisição MCP autenticada via ``?token=`` (AuthMiddleware) → contextvars
corretas. O caminho legado (sem token) permanece byte-idêntico.
"""

import logging
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
from app.mcp_server import (
    _log_machine_divergence_if_any,
    _usage_user_id,
    user_id_var,
)
from app.middleware.team_auth import AuthMiddleware
from app.models import USER_TYPE_PERSON, Machine, MachineStatus, User
from app.routers import agent_tokens as agent_tokens_module
from app.routers import auth as auth_module
from app.routers import provision as provision_module
from app.utils import identity_links
from app.utils.logging_context import auth_method_var, auth_user_var, machine_var

SECRET = "segredo-de-teste-com-32-bytes-ok!"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_ALLOWED_DOMAIN", "sysmo.com.br")
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setattr(auth_module, "_count_memories_for_hostname", lambda h: 7)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database_module, "SessionLocal", Session)
    identity_links.invalidate_identity_link_cache()
    yield Session
    identity_links.invalidate_identity_link_cache()
    engine.dispose()


def _seed_person(Session, sub="sub-1"):
    db = Session()
    try:
        user = User(user_id=sub, user_type=USER_TYPE_PERSON, google_sub=sub)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


class TestUsageUserId:
    def test_agent_token_atribui_pessoa(self):
        tokens = [
            auth_method_var.set("agent_token"),
            auth_user_var.set("person-uuid"),
            user_id_var.set("DESKTOP-01"),
        ]
        try:
            assert _usage_user_id() == "person-uuid"
        finally:
            user_id_var.reset(tokens[2])
            auth_user_var.reset(tokens[1])
            auth_method_var.reset(tokens[0])

    def test_legado_atribui_hostname(self):
        token = user_id_var.set("DESKTOP-01")
        try:
            assert _usage_user_id() == "DESKTOP-01"
        finally:
            user_id_var.reset(token)

    def test_sem_hostname_cai_no_sentinel(self):
        assert _usage_user_id() == "unknown-host"


class TestMachineDivergence:
    def test_divergencia_gera_warning(self, env, caplog):
        person_id = _seed_person(env)
        db = env()
        try:
            db.add(
                Machine(
                    hostname="DESKTOP-01",
                    linked_user_id=person_id,
                    status=MachineStatus.linked,
                )
            )
            db.commit()
        finally:
            db.close()

        tokens = [
            auth_method_var.set("agent_token"),
            auth_user_var.set(str(person_id)),
        ]
        try:
            with caplog.at_level(logging.WARNING):
                _log_machine_divergence_if_any("OUTRA-MAQUINA")
        finally:
            auth_user_var.reset(tokens[1])
            auth_method_var.reset(tokens[0])

        assert any("maquina divergente" in r.getMessage() for r in caplog.records)

    def test_maquina_vinculada_nao_loga(self, env, caplog):
        person_id = _seed_person(env)
        db = env()
        try:
            db.add(
                Machine(
                    hostname="DESKTOP-01",
                    linked_user_id=person_id,
                    status=MachineStatus.linked,
                )
            )
            db.commit()
        finally:
            db.close()

        tokens = [
            auth_method_var.set("agent_token"),
            auth_user_var.set(str(person_id)),
        ]
        try:
            with caplog.at_level(logging.WARNING):
                _log_machine_divergence_if_any("DESKTOP-01")
        finally:
            auth_user_var.reset(tokens[1])
            auth_method_var.reset(tokens[0])

        assert not any("maquina divergente" in r.getMessage() for r in caplog.records)

    def test_legado_sem_token_nao_loga(self, env, caplog):
        with caplog.at_level(logging.WARNING):
            _log_machine_divergence_if_any("DESKTOP-01")
        assert not any("maquina divergente" in r.getMessage() for r in caplog.records)


class TestEndToEndBackend:
    """login → onboarding → token → provision → chamada MCP com ?token=."""

    @pytest.fixture
    def client(self, env, monkeypatch):
        monkeypatch.setattr(
            auth_module,
            "_verify_google_id_token",
            lambda raw: {
                "sub": "sub-e2e",
                "email": "e2e@sysmo.com.br",
                "name": "E2E",
                "hd": "sysmo.com.br",
            },
        )

        app = FastAPI()
        app.add_middleware(AuthMiddleware, mode="warn", token_to_team={})
        app.include_router(auth_module.router)
        app.include_router(agent_tokens_module.router)
        app.include_router(provision_module.router)

        @app.post("/mcp/claude-code/http/{host}")
        def mcp(host: str):
            return {
                "method": auth_method_var.get() or "legacy",
                "user": auth_user_var.get() or None,
                "machine": machine_var.get() or None,
                "path_host": host,
            }

        def _override():
            db = env()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override
        return TestClient(app), env

    def test_fluxo_completo_atribui_pessoa_maquina_agente(self, client):
        http, Session = client

        # 1) Login Google → JWT de sessão.
        login = http.post("/api/v1/auth/google", json={"id_token": "fake"}).json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        assert login["first_login"] is True

        # 2) Onboarding vincula a máquina.
        onboarding = http.post(
            "/api/v1/auth/onboarding",
            json={"hostname": "DESKTOP-E2E", "group_name": "Equipe X"},
            headers=headers,
        )
        assert onboarding.status_code == 200

        # 3) Token de agente.
        raw_token = http.post("/api/v1/agent-token", headers=headers).json()["token"]

        # 4) Provision embute o token na URL MCP.
        recipe = http.get(
            f"/provision?host=claude-code&token={raw_token}"
        ).json()
        mcp_url_template = recipe["mcp_config"]["content"]["mcpServers"]["mem0"]["url"]
        assert f"token={raw_token}" in mcp_url_template
        mcp_path = mcp_url_template.split("http://testserver")[-1].replace(
            "{hostname}", "DESKTOP-E2E"
        )

        # 5) Chamada MCP com a URL gerada: identidade completa resolvida.
        body = http.post(mcp_path).json()
        person_id = login["user"]["id"]
        assert body == {
            "method": "agent_token",
            "user": person_id,
            "machine": "DESKTOP-E2E",
            "path_host": "DESKTOP-E2E",
        }

        # Resolução dinâmica: memórias legadas da máquina pertencem à pessoa.
        assert identity_links.resolve_person_for_hostname("DESKTOP-E2E") == person_id

    def test_sem_token_comportamento_legado_intacto(self, client):
        http, _ = client
        body = http.post("/mcp/claude-code/http/DESKTOP-LEGADO").json()
        assert body["method"] == "legacy"
        assert body["user"] is None

    def test_token_revogado_administrativamente_bloqueia_mcp(self, client):
        from app.models import AgentToken, get_current_utc_time

        http, Session = client
        login = http.post("/api/v1/auth/google", json={"id_token": "fake"}).json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        raw_token = http.post("/api/v1/agent-token", headers=headers).json()["token"]

        assert (
            http.post(f"/mcp/claude-code/http/H?token={raw_token}").status_code == 200
        )
        # ADR-008: sem DELETE na API; a válvula de emergência é administrativa
        # (UPDATE direto no banco) e o middleware continua honrando-a.
        db = Session()
        try:
            row = db.query(AgentToken).one()
            row.revoked_at = get_current_utc_time()
            db.commit()
        finally:
            db.close()
        assert (
            http.post(f"/mcp/claude-code/http/H?token={raw_token}").status_code == 401
        )
