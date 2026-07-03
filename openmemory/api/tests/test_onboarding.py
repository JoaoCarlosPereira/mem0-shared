"""Testes da task_05 (feature auth Google): onboarding e resolução dinâmica.

Cobre o vínculo máquina→conta (com e sem usuário legado), idempotência,
conflito 409 com trilha em ``link_audit_logs`` e o cache de
``identity_links``. A contagem de memórias (Qdrant) é monkeypatchada — o
endpoint nunca toca payloads (ADR-005).
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
from app.models import (
    USER_TYPE_LEGACY_HOST,
    USER_TYPE_PERSON,
    Group,
    LinkAuditLog,
    Machine,
    MachineStatus,
    User,
)
from app.routers import auth as auth_module
from app.utils import identity_links
from app.utils.session_jwt import issue_session_jwt

SECRET = "segredo-de-teste-com-32-bytes-ok!"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setattr(auth_module, "_count_memories_for_hostname", lambda h: 42)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(database_module, "SessionLocal", Session)
    identity_links.invalidate_identity_link_cache()

    app = FastAPI()
    app.include_router(auth_module.router)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield Session, TestClient(app)
    identity_links.invalidate_identity_link_cache()
    engine.dispose()


def _person(Session, sub="sub-1"):
    db = Session()
    try:
        user = User(user_id=sub, user_type=USER_TYPE_PERSON, google_sub=sub)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, {"Authorization": f"Bearer {issue_session_jwt(user_id=user.id)}"}
    finally:
        db.close()


def _legacy(Session, hostname="DESKTOP-01"):
    db = Session()
    try:
        user = User(user_id=hostname)  # user_type default legacy_host
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


class TestOnboarding:
    def test_vinculo_com_legado_retorna_contagem_e_grupo(self, env):
        Session, client = env
        legacy_id = _legacy(Session, "DESKTOP-01")
        user_id, headers = _person(Session)

        resp = client.post(
            "/api/v1/auth/onboarding",
            json={"hostname": "DESKTOP-01", "group_name": "Equipe Fiscal"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "linked": True,
            "hostname": "DESKTOP-01",
            "group": "Equipe Fiscal",
            "memories_count": 42,
            "legacy_user_linked": True,
        }

        db = Session()
        try:
            machine = db.query(Machine).one()
            assert machine.status == MachineStatus.linked
            assert machine.linked_user_id == user_id
            assert machine.legacy_user_id == legacy_id
            assert machine.linked_by == user_id and machine.linked_at is not None
            logs = db.query(LinkAuditLog).all()
            assert [log.action for log in logs] == ["link"]
            assert logs[0].detail["group"] == "Equipe Fiscal"
            person = db.query(User).filter(User.id == user_id).one()
            group = db.query(Group).filter(Group.name == "Equipe Fiscal").one()
            assert person.group_id == group.id
            legacy = db.query(User).filter(User.id == legacy_id).one()
            assert legacy.group_id is None, "grupo do legado não muda no onboarding"
        finally:
            db.close()

    def test_hostname_inedito_vincula_sem_legado(self, env):
        Session, client = env
        _, headers = _person(Session)

        body = client.post(
            "/api/v1/auth/onboarding",
            json={"hostname": "NOVA-MAQ", "group_name": None},
            headers=headers,
        ).json()
        assert body["legacy_user_linked"] is False
        assert body["group"] == "Default"

    def test_repeticao_idempotente(self, env):
        Session, client = env
        _legacy(Session)
        _, headers = _person(Session)
        payload = {"hostname": "DESKTOP-01", "group_name": "Equipe Fiscal"}

        assert client.post("/api/v1/auth/onboarding", json=payload, headers=headers).status_code == 200
        assert client.post("/api/v1/auth/onboarding", json=payload, headers=headers).status_code == 200

        db = Session()
        try:
            assert db.query(Machine).count() == 1
            assert db.query(LinkAuditLog).filter(LinkAuditLog.action == "link").count() == 1
        finally:
            db.close()

    def test_maquina_de_outra_conta_409_com_conflito_registrado(self, env):
        Session, client = env
        _, headers_a = _person(Session, "sub-a")
        _, headers_b = _person(Session, "sub-b")
        payload = {"hostname": "DESKTOP-01"}

        assert client.post("/api/v1/auth/onboarding", json=payload, headers=headers_a).status_code == 200
        resp = client.post("/api/v1/auth/onboarding", json=payload, headers=headers_b)
        assert resp.status_code == 409

        db = Session()
        try:
            machine = db.query(Machine).one()
            assert machine.status == MachineStatus.conflict
            conflicts = (
                db.query(LinkAuditLog)
                .filter(LinkAuditLog.action == "conflict_detected")
                .all()
            )
            assert len(conflicts) == 1
        finally:
            db.close()

    def test_hostname_vazio_422(self, env):
        Session, client = env
        _, headers = _person(Session)
        resp = client.post(
            "/api/v1/auth/onboarding", json={"hostname": "  "}, headers=headers
        )
        assert resp.status_code == 422

    def test_fluxo_completo_login_onboarding_me(self, env, monkeypatch):
        Session, client = env
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
        monkeypatch.setenv("AUTH_ALLOWED_DOMAIN", "sysmo.com.br")

        token = client.post(
            "/api/v1/auth/google", json={"id_token": "fake"}
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        client.post(
            "/api/v1/auth/onboarding",
            json={"hostname": "DESKTOP-E2E", "group_name": "Equipe X"},
            headers=headers,
        )
        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert me["machine"]["hostname"] == "DESKTOP-E2E"
        assert me["group"] == "Equipe X"


class TestMachineSuggestions:
    def test_sem_sessao_401(self, env):
        Session, client = env
        assert client.get("/api/v1/auth/machine-suggestions").status_code == 401

    def test_lista_apenas_maquinas_nao_vinculadas(self, env):
        Session, client = env
        user_id, headers = _person(Session)
        db = Session()
        try:
            db.add(Machine(hostname="LIVRE-01"))
            db.add(Machine(hostname="LIVRE-02"))
            db.add(
                Machine(
                    hostname="OCUPADA",
                    linked_user_id=user_id,
                    status=MachineStatus.linked,
                )
            )
            db.commit()
        finally:
            db.close()

        body = client.get("/api/v1/auth/machine-suggestions", headers=headers).json()
        assert body["unlinked_hostnames"] == ["LIVRE-01", "LIVRE-02"]

    def test_dns_reverso_sugere_hostname_com_grafia_do_cadastro(self, env, monkeypatch):
        from app.routers import auth as auth_mod

        Session, client = env
        _, headers = _person(Session)
        db = Session()
        try:
            db.add(Machine(hostname="S0293"))
            db.commit()
        finally:
            db.close()

        # DNS reverso devolve minúsculo/FQDN; a sugestão usa a grafia cadastrada.
        monkeypatch.setattr(
            auth_mod, "_reverse_dns_hostname", lambda ip: "s0293"
        )
        body = client.get(
            "/api/v1/auth/machine-suggestions",
            headers={**headers, "x-forwarded-for": "192.168.3.50"},
        ).json()
        assert body["detected_hostname"] == "S0293"

    def test_sem_ip_resolvivel_detected_none(self, env):
        Session, client = env
        _, headers = _person(Session)
        # TestClient usa o host sentinela "testclient" (sem X-Forwarded-For):
        # o DNS reverso é pulado e a detecção volta vazia.
        body = client.get("/api/v1/auth/machine-suggestions", headers=headers).json()
        assert body["detected_hostname"] is None


class TestIdentityLinksCache:
    def test_resolve_apos_vinculo_e_none_para_desconhecido(self, env):
        Session, client = env
        user_id, headers = _person(Session)
        client.post(
            "/api/v1/auth/onboarding", json={"hostname": "DESKTOP-01"}, headers=headers
        )

        assert identity_links.resolve_person_for_hostname("DESKTOP-01") == str(user_id)
        assert identity_links.resolve_person_for_hostname("OUTRA") is None
        assert identity_links.resolve_person_for_hostname("") is None

    def test_invalidacao_reflete_mudanca_imediata(self, env):
        Session, client = env
        user_id, headers = _person(Session)
        client.post(
            "/api/v1/auth/onboarding", json={"hostname": "DESKTOP-01"}, headers=headers
        )
        assert identity_links.resolve_person_for_hostname("DESKTOP-01") == str(user_id)

        # Desvincula direto no banco e invalida — a resolução muda na hora.
        db = Session()
        try:
            machine = db.query(Machine).one()
            machine.linked_user_id = None
            machine.status = MachineStatus.unlinked
            db.commit()
        finally:
            db.close()
        identity_links.invalidate_identity_link_cache("DESKTOP-01")
        assert identity_links.resolve_person_for_hostname("DESKTOP-01") is None

    def test_falha_de_banco_nao_propaga(self, env, monkeypatch):
        def _boom(hostname):
            raise RuntimeError("banco fora")

        monkeypatch.setattr(identity_links, "_query_linked_person", _boom)
        identity_links.invalidate_identity_link_cache()
        assert identity_links.resolve_person_for_hostname("QUALQUER") is None
