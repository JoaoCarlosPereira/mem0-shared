"""Testes do Device Flow (ADR-007): login Google sem URL de redirect.

As chamadas ao Google são monkeypatchadas (``_post_form``) — nenhum teste toca
a rede. O ponto central: o polling conclui o login pelo MESMO caminho do fluxo
de redirect (``_complete_google_login``), então a restrição ao domínio
corporativo configurado (``AUTH_ALLOWED_DOMAIN``) vale igualmente.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User
from app.routers import auth as auth_module

DOMAIN = "sysmo.com.br"
SECRET = "segredo-de-teste-com-32-bytes-ok!"


def _claims(**overrides):
    base = {
        "sub": "google-sub-device",
        "email": "joao@sysmo.com.br",
        "name": "João Carlos",
        "picture": None,
        "hd": DOMAIN,
    }
    base.update(overrides)
    return base


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_ALLOWED_DOMAIN", DOMAIN)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")

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


def _mock_google(monkeypatch, responses):
    """Enfileira respostas do Google por URL; registra as chamadas feitas."""
    calls = []

    def _fake_post_form(url, data):
        calls.append((url, data))
        queue = responses[url]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(auth_module, "_post_form", _fake_post_form)
    return calls


DEVICE_OK = {
    "_status": 200,
    "device_code": "dev-123",
    "user_code": "ABCD-EFGH",
    "verification_url": "https://www.google.com/device",
    "interval": 5,
    "expires_in": 1800,
}


class TestDeviceStart:
    def test_start_devolve_codigo_e_url(self, client, monkeypatch):
        calls = _mock_google(
            monkeypatch, {auth_module.GOOGLE_DEVICE_CODE_URL: [DEVICE_OK]}
        )
        resp = client.post("/api/v1/auth/google/device/start")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_code"] == "ABCD-EFGH"
        assert body["verification_url"] == "https://www.google.com/device"
        assert body["device_code"] == "dev-123"
        url, data = calls[0]
        assert data["client_id"] == "cid.apps.googleusercontent.com"
        assert data["scope"] == "openid email profile"

    def test_start_sem_client_secret_503(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
        assert client.post("/api/v1/auth/google/device/start").status_code == 503

    def test_start_sem_dominio_configurado_503(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_ALLOWED_DOMAIN", "")
        assert client.post("/api/v1/auth/google/device/start").status_code == 503

    def test_start_google_indisponivel_502(self, client, monkeypatch):
        _mock_google(
            monkeypatch, {auth_module.GOOGLE_DEVICE_CODE_URL: [{"_status": 500}]}
        )
        assert client.post("/api/v1/auth/google/device/start").status_code == 502

    def test_client_dedicado_do_device_flow_tem_preferencia(self, client, monkeypatch):
        """ADR-009: com GOOGLE_DEVICE_CLIENT_ID/SECRET definidos (client tipo
        TVs), o device flow os usa em vez do client Web principal."""
        monkeypatch.setenv("GOOGLE_DEVICE_CLIENT_ID", "tv-cid.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_DEVICE_CLIENT_SECRET", "tv-csec")
        calls = _mock_google(
            monkeypatch, {auth_module.GOOGLE_DEVICE_CODE_URL: [DEVICE_OK]}
        )
        assert client.post("/api/v1/auth/google/device/start").status_code == 200
        _, data = calls[0]
        assert data["client_id"] == "tv-cid.apps.googleusercontent.com"


class TestDevicePoll:
    def _poll(self, client):
        return client.post(
            "/api/v1/auth/google/device/poll", json={"device_code": "dev-123"}
        )

    def test_pendente_e_slow_down(self, client, monkeypatch):
        _mock_google(
            monkeypatch,
            {
                auth_module.GOOGLE_TOKEN_URL: [
                    {"_status": 428, "error": "authorization_pending"},
                    {"_status": 403, "error": "slow_down"},
                ]
            },
        )
        assert self._poll(client).json()["status"] == "pending"
        assert self._poll(client).json()["status"] == "slow_down"

    def test_codigo_expirado_410(self, client, monkeypatch):
        _mock_google(
            monkeypatch,
            {auth_module.GOOGLE_TOKEN_URL: [{"_status": 400, "error": "expired_token"}]},
        )
        assert self._poll(client).status_code == 410

    def test_negado_pelo_usuario_403(self, client, monkeypatch):
        _mock_google(
            monkeypatch,
            {auth_module.GOOGLE_TOKEN_URL: [{"_status": 403, "error": "access_denied"}]},
        )
        assert self._poll(client).status_code == 403

    def test_autorizado_cria_pessoa_e_emite_jwt(self, client, monkeypatch):
        calls = _mock_google(
            monkeypatch,
            {
                auth_module.GOOGLE_TOKEN_URL: [
                    {"_status": 200, "id_token": "fake-id-token"}
                ]
            },
        )
        monkeypatch.setattr(
            auth_module, "_verify_google_id_token", lambda raw: _claims()
        )
        resp = self._poll(client)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["first_login"] is True
        claims = pyjwt.decode(body["access_token"], SECRET, algorithms=["HS256"])
        assert claims["email"] == "joao@sysmo.com.br"
        # Polling autentica com id+secret (exigência do device flow).
        _, data = calls[0]
        assert data["client_secret"] == "csec"
        assert data["grant_type"].endswith("device_code")

        # Segundo login do mesmo sub: mesma pessoa, first_login False.
        resp2 = self._poll(client)
        assert resp2.json()["first_login"] is False
        db = client.db_session_factory()
        try:
            assert (
                db.query(User).filter(User.google_sub == "google-sub-device").count()
                == 1
            )
        finally:
            db.close()

    def test_conta_fora_do_dominio_corporativo_403(self, client, monkeypatch):
        """O porém do usuário: device flow SÓ aceita a conta corporativa
        configurada no install (AUTH_ALLOWED_DOMAIN) — mesmo caminho do redirect."""
        _mock_google(
            monkeypatch,
            {auth_module.GOOGLE_TOKEN_URL: [{"_status": 200, "id_token": "fake"}]},
        )
        monkeypatch.setattr(
            auth_module,
            "_verify_google_id_token",
            lambda raw: _claims(hd="gmail-pessoal-sem-hd", email="x@gmail.com"),
        )
        resp = self._poll(client)
        assert resp.status_code == 403
        assert DOMAIN in resp.json()["detail"]

        db = client.db_session_factory()
        try:
            assert db.query(User).count() == 0, "conta recusada não pode ser criada"
        finally:
            db.close()

    def test_conta_pessoal_sem_hd_403(self, client, monkeypatch):
        _mock_google(
            monkeypatch,
            {auth_module.GOOGLE_TOKEN_URL: [{"_status": 200, "id_token": "fake"}]},
        )
        monkeypatch.setattr(
            auth_module, "_verify_google_id_token", lambda raw: _claims(hd=None)
        )
        assert self._poll(client).status_code == 403

    def test_id_token_invalido_401(self, client, monkeypatch):
        _mock_google(
            monkeypatch,
            {auth_module.GOOGLE_TOKEN_URL: [{"_status": 200, "id_token": "fake"}]},
        )

        def _boom(raw):
            raise ValueError("assinatura inválida")

        monkeypatch.setattr(auth_module, "_verify_google_id_token", _boom)
        assert self._poll(client).status_code == 401
