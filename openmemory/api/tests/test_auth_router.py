"""Testes da task_02 (feature auth Google): /auth/google e /auth/me.

App FastAPI isolado (padrão do repo) com SQLite em memória e a verificação do
ID token do Google substituída por monkeypatch — nenhum teste depende de rede.
"""

import uuid

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import (
    USER_TYPE_PERSON,
    Group,
    Machine,
    MachineStatus,
    User,
    get_current_utc_time,
)
from app.routers import auth as auth_module

DOMAIN = "sysmo.com.br"
SECRET = "segredo-de-teste-com-32-bytes-ok!"  # >=32 bytes (RFC 7518)


def _claims(**overrides):
    base = {
        "sub": "google-sub-123",
        "email": "joao@sysmo.com.br",
        "name": "João Carlos",
        "picture": "https://lh3.example/avatar.png",
        "hd": DOMAIN,
    }
    base.update(overrides)
    return base


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_ALLOWED_DOMAIN", DOMAIN)
    monkeypatch.delenv("AUTH_JWT_TTL_SECONDS", raising=False)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    app = FastAPI()
    app.include_router(auth_module.router)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    test_client = TestClient(app)
    test_client.db_session_factory = Session
    yield test_client


def _login(client, monkeypatch, **claim_overrides):
    monkeypatch.setattr(
        auth_module, "_verify_google_id_token", lambda raw: _claims(**claim_overrides)
    )
    return client.post("/api/v1/auth/google", json={"id_token": "fake"})


class TestLoginWithGoogle:
    def test_dominio_permitido_cria_person_e_first_login_true(self, client, monkeypatch):
        resp = _login(client, monkeypatch)
        assert resp.status_code == 200
        body = resp.json()
        assert body["first_login"] is True
        assert body["user"]["user_type"] == USER_TYPE_PERSON
        assert body["user"]["email"] == "joao@sysmo.com.br"

        claims = pyjwt.decode(body["access_token"], SECRET, algorithms=["HS256"])
        assert claims["sub"] == body["user"]["id"]
        assert "exp" in claims and claims["email"] == "joao@sysmo.com.br"

    def test_segundo_login_mesmo_sub_nao_duplica_e_first_login_false(
        self, client, monkeypatch
    ):
        _login(client, monkeypatch)
        resp = _login(client, monkeypatch, email="novo-email@sysmo.com.br")
        assert resp.status_code == 200
        assert resp.json()["first_login"] is False
        assert resp.json()["user"]["email"] == "novo-email@sysmo.com.br"

        db = client.db_session_factory()
        try:
            people = db.query(User).filter(User.google_sub == "google-sub-123").count()
        finally:
            db.close()
        assert people == 1

    def test_hd_divergente_retorna_403(self, client, monkeypatch):
        resp = _login(client, monkeypatch, hd="outra-empresa.com")
        assert resp.status_code == 403
        assert DOMAIN in resp.json()["detail"]

    def test_hd_ausente_conta_pessoal_retorna_403(self, client, monkeypatch):
        resp = _login(client, monkeypatch, hd=None)
        assert resp.status_code == 403

    def test_id_token_invalido_retorna_401(self, client, monkeypatch):
        def _boom(raw):
            raise ValueError("assinatura inválida")

        monkeypatch.setattr(auth_module, "_verify_google_id_token", _boom)
        resp = client.post("/api/v1/auth/google", json={"id_token": "fake"})
        assert resp.status_code == 401

    def test_sem_dominio_configurado_fail_closed_503(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_ALLOWED_DOMAIN", "")
        resp = _login(client, monkeypatch)
        assert resp.status_code == 503


class TestAudienceValidation:
    """ADR-009: dois clients OAuth coexistem — o aud do ID token pode ser o
    client Web (redirect) OU o client TVs (device flow)."""

    def _verify_with_aud(self, monkeypatch, aud):
        import google.oauth2.id_token as google_id_token

        monkeypatch.setattr(
            google_id_token,
            "verify_oauth2_token",
            lambda raw, req, audience=None: _claims(aud=aud),
        )
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "web-cid")
        monkeypatch.setenv("GOOGLE_DEVICE_CLIENT_ID", "tv-cid")
        from app.routers.auth import _verify_google_id_token

        return _verify_google_id_token("fake")

    def test_aud_do_client_web_aceito(self, client, monkeypatch):
        claims = self._verify_with_aud(monkeypatch, "web-cid")
        assert claims["aud"] == "web-cid"

    def test_aud_do_client_device_aceito(self, client, monkeypatch):
        claims = self._verify_with_aud(monkeypatch, "tv-cid")
        assert claims["aud"] == "tv-cid"

    def test_aud_desconhecido_rejeitado(self, client, monkeypatch):
        with pytest.raises(ValueError):
            self._verify_with_aud(monkeypatch, "client-de-terceiro")


class TestMe:
    def test_fluxo_login_me_retorna_mesmo_usuario(self, client, monkeypatch):
        token = _login(client, monkeypatch).json()["access_token"]
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["email"] == "joao@sysmo.com.br"
        assert body["machine"] is None
        assert body["group"] is None

    def test_me_com_maquina_e_grupo_vinculados(self, client, monkeypatch):
        login = _login(client, monkeypatch).json()
        token = login["access_token"]
        user_pk = uuid.UUID(login["user"]["id"])

        db = client.db_session_factory()
        try:
            group = Group(name="Equipe Fiscal")
            db.add(group)
            db.flush()
            user = db.query(User).filter(User.id == user_pk).one()
            user.group_id = group.id
            db.add(
                Machine(
                    hostname="DESKTOP-01",
                    linked_user_id=user_pk,
                    status=MachineStatus.linked,
                    linked_at=get_current_utc_time(),
                )
            )
            db.commit()
        finally:
            db.close()

        body = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        ).json()
        assert body["machine"]["hostname"] == "DESKTOP-01"
        assert body["group"] == "Equipe Fiscal"

    def test_me_sem_authorization_retorna_401(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_me_com_jwt_expirado_retorna_401(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_JWT_TTL_SECONDS", "-10")
        token = _login(client, monkeypatch).json()["access_token"]
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    def test_me_com_jwt_de_outro_segredo_retorna_401(self, client):
        forged = pyjwt.encode(
            {"sub": str(uuid.uuid4())}, "outro-segredo", algorithm="HS256"
        )
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}
        )
        assert resp.status_code == 401
