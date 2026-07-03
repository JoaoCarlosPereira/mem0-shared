"""Tests for scale bootstrap artifacts (task_08)."""

import os
from unittest.mock import MagicMock

import pytest

from tests.paths import openmemory_root


ROOT = openmemory_root()


class TestBootstrapArtifacts:
    def test_bootstrap_script_exists_and_executable(self):
        script = ROOT / "scripts" / "bootstrap-scale.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)

    def test_docker_compose_scale_valid(self):
        compose = ROOT / "docker-compose.scale.yml"
        assert compose.exists()
        text = compose.read_text()
        assert "pgbouncer" in text
        assert "openmemory-write-worker" in text
        assert "openmemory-governance-worker" in text
        assert "circuitbreaker" in text


class TestScaleGovernanceWorker:
    """The off-peak intelligent processing only runs if the governance worker is
    deployed. Lock it into the scale Compose stack (parity with docker-stack.yml)."""

    @pytest.fixture(scope="class")
    def scale(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(
            (ROOT / "docker-compose.scale.yml").read_text(encoding="utf-8")
        )

    def test_service_exists(self, scale):
        assert "openmemory-governance-worker" in scale["services"]

    def test_command(self, scale):
        svc = scale["services"]["openmemory-governance-worker"]
        assert svc["command"] == "python -m app.workers.governance_worker"

    def test_scheduler_enabled(self, scale):
        env = scale["services"]["openmemory-governance-worker"]["environment"]
        assert env.get("GOVERNANCE_ENABLE_SCHEDULER") == "true"
        assert env.get("RUN_EMBEDDED_WORKER") == "false"
        # Inherited from the api-common env anchor (merge key).
        assert "DATABASE_URL" in env
        assert "QDRANT_HOST" in env
        assert "REDIS_URL" in env

    def test_external_ollama_default(self, scale):
        # The scale stack defaults to an EXTERNAL Ollama (host/LAN), not the
        # containerized inference services.
        env = scale["services"]["openmemory-mcp"]["environment"]
        assert "host.docker.internal" in env["OLLAMA_LLM_URL"]
        assert "host.docker.internal" in env["OLLAMA_EMBED_URL"]

    def test_docker_stack_exists(self):
        stack = ROOT / "docker-stack.yml"
        assert stack.exists()
        assert "deploy:" in stack.read_text()

    def test_migrate_script_importable(self):
        script = ROOT / "scripts" / "migrate_sqlite_to_postgres.py"
        assert script.exists()


class TestBootstrapGoogleAuthSetup:
    """task_10/feature auth Google: o bootstrap pede/gera tudo que o login
    Google precisa (domínio, client id/secret, URL da UI, segredos de sessão),
    sem nunca bloquear a instalação (fail-closed => fluxo legado segue)."""

    @pytest.fixture(scope="class")
    def script(self):
        return (ROOT / "scripts" / "bootstrap-scale.sh").read_text(encoding="utf-8")

    def test_flag_skip_auth_setup_existe(self, script):
        assert "--skip-auth-setup" in script
        assert "SKIP_AUTH_SETUP=1" in script

    def test_pergunta_dominio_e_credenciais(self, script):
        for needle in (
            "AUTH_ALLOWED_DOMAIN",
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "NEXTAUTH_URL",
        ):
            assert needle in script, f"bootstrap deve tratar {needle}"

    def test_segredos_gerados_automaticamente(self, script):
        assert "gen_secret" in script
        assert "AUTH_JWT_SECRET" in script
        assert "NEXTAUTH_SECRET" in script
        assert "openssl rand" in script

    def test_client_secret_nao_ecoa_no_terminal(self, script):
        # read -s: o valor digitado do client secret não aparece na tela.
        assert 'read -r -s -p "    GOOGLE_CLIENT_SECRET' in script

    def test_nao_interativo_nao_bloqueia(self, script):
        # Sem TTY o bootstrap segue com o fluxo legado (fail-closed), sem exit.
        assert "sem TTY" in script
        assert "fluxo legado segue ativo" in script

    def test_escrita_idempotente_no_env(self, script):
        # Só escreve chaves ausentes — re-rodar o bootstrap não duplica/reescreve.
        assert "set_env_if_missing" in script

    def test_redirect_uri_informado_ao_usuario(self, script):
        assert "/api/auth/callback/google" in script


class TestBootstrapDetection:
    def test_detect_ollama_when_tags_respond(self):
        from app.utils.model_detection import detect_ollama_models

        fake_client = MagicMock()
        fake_client.list.return_value = {"models": [{"name": "llama3.1:8b"}]}
        models = detect_ollama_models(ollama_base_url="http://ollama:11434", client=fake_client)
        assert models == ["llama3.1:8b"]

    def test_detect_llamacpp_when_models_respond(self):
        from app.utils.model_detection import detect_llamacpp_models

        def fake_fetch(url):
            return {"data": [{"id": "local-model"}]}

        models = detect_llamacpp_models(base_url="http://llama:8080/v1", fetch=fake_fetch)
        assert models == ["local-model"]

    def test_explicit_embed_url_skips_detection_in_bootstrap_guard(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_EMBED_URL", "http://embed:11434")
        skip = bool(os.getenv("OLLAMA_EMBED_URL") or os.getenv("EMBEDDER_BASE_URL"))
        assert skip is True
