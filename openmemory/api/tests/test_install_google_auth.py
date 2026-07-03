"""Testes do instalador (install.py) — etapa de login Google (feature auth Google).

Carrega o install.py da raiz do repositório via importlib (sem executar main) e
exercita ``configure_google_auth`` de verdade contra um .env temporário:
flags/prompt, geração única dos segredos, idempotência e fail-closed.
"""

import importlib.util
from types import SimpleNamespace

import pytest

from tests.paths import openmemory_root

_INSTALL_PATH = openmemory_root().parent / "install.py"
_spec = importlib.util.spec_from_file_location("install_under_test", _INSTALL_PATH)
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)


def _args(**overrides):
    base = {
        "google_domain": None,
        "google_client_id": None,
        "google_client_secret": None,
        "ui_url": None,
        "skip_google_auth": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def compose_env(tmp_path):
    return tmp_path / ".env"


class TestConfigureGoogleAuthFlags:
    def test_flags_configuram_tudo_e_geram_segredos(self, compose_env):
        result = install.configure_google_auth(
            _args(
                google_domain="sysmo.com.br",
                google_client_id="cid.apps.googleusercontent.com",
                google_client_secret="csec",
                ui_url="http://192.168.0.10:3000",
            ),
            compose_env,
            interactive=False,
        )
        assert result is True
        assert install.read_env(compose_env, "AUTH_ALLOWED_DOMAIN") == "sysmo.com.br"
        assert install.read_env(compose_env, "GOOGLE_CLIENT_ID") == "cid.apps.googleusercontent.com"
        assert install.read_env(compose_env, "GOOGLE_CLIENT_SECRET") == "csec"
        assert install.read_env(compose_env, "NEXTAUTH_URL") == "http://192.168.0.10:3000"
        # Segredos gerados automaticamente com tamanho seguro (>= 32 bytes).
        for key in ("AUTH_JWT_SECRET", "NEXTAUTH_SECRET"):
            value = install.read_env(compose_env, key)
            assert value and len(value) >= 43, f"{key} deve ser gerado (>=32 bytes)"

    def test_idempotente_nao_regrava_segredos(self, compose_env):
        args = _args(
            google_domain="sysmo.com.br",
            google_client_id="cid",
            google_client_secret="csec",
        )
        install.configure_google_auth(args, compose_env, interactive=False)
        jwt1 = install.read_env(compose_env, "AUTH_JWT_SECRET")
        na1 = install.read_env(compose_env, "NEXTAUTH_SECRET")

        install.configure_google_auth(args, compose_env, interactive=False)
        assert install.read_env(compose_env, "AUTH_JWT_SECRET") == jwt1
        assert install.read_env(compose_env, "NEXTAUTH_SECRET") == na1

    def test_config_existente_no_env_e_reconhecida_sem_flags(self, compose_env):
        install.set_env(compose_env, "AUTH_ALLOWED_DOMAIN", "sysmo.com.br")
        install.set_env(compose_env, "GOOGLE_CLIENT_ID", "cid")
        install.set_env(compose_env, "GOOGLE_CLIENT_SECRET", "csec")
        result = install.configure_google_auth(_args(), compose_env, interactive=False)
        assert result is True
        assert install.read_env(compose_env, "AUTH_JWT_SECRET")

    def test_sem_config_nao_interativo_fail_closed(self, compose_env):
        result = install.configure_google_auth(_args(), compose_env, interactive=False)
        assert result is False
        # Nada de login gravado — fluxo legado segue.
        assert install.read_env(compose_env, "AUTH_ALLOWED_DOMAIN") is None
        assert install.read_env(compose_env, "AUTH_JWT_SECRET") is None


class TestConfigureGoogleAuthInterativo:
    def test_prompts_configuram_login(self, compose_env, monkeypatch):
        answers = iter([
            "sysmo.com.br",                # domínio
            "cid.apps.googleusercontent.com",  # client id
            "",                             # URL da UI (Enter = default sugerido)
        ])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
        monkeypatch.setattr(install, "_ask_hidden", lambda prompt="": "csec")

        result = install.configure_google_auth(
            _args(), compose_env, interactive=True, ui_url="http://192.168.0.10:3000"
        )
        assert result is True
        assert install.read_env(compose_env, "NEXTAUTH_URL") == "http://192.168.0.10:3000"
        assert install.read_env(compose_env, "GOOGLE_CLIENT_SECRET") == "csec"

    def test_dominio_em_branco_pula_sem_bloquear(self, compose_env, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt="": "")
        result = install.configure_google_auth(_args(), compose_env, interactive=True)
        assert result is False
        assert install.read_env(compose_env, "AUTH_ALLOWED_DOMAIN") is None

    def test_flag_skip_google_auth_nao_pergunta(self, compose_env, monkeypatch):
        def _boom(prompt=""):
            raise AssertionError("não deveria perguntar com --skip-google-auth")

        monkeypatch.setattr("builtins.input", _boom)
        result = install.configure_google_auth(
            _args(skip_google_auth=True), compose_env, interactive=True
        )
        assert result is False


@pytest.fixture(scope="module")
def source():
    return _INSTALL_PATH.read_text(encoding="utf-8")


class TestInstallerWiring:
    """Trava o encaixe nos fluxos: instalação e --update chamam a etapa."""

    def test_run_production_chama_configure_google_auth(self, source):
        assert "configure_google_auth(args, compose_env, interactive=not args.yes" in source

    def test_run_update_chama_configure_google_auth(self, source):
        # No --update a etapa roda antes do rebuild, sem bloquear (TTY-aware).
        assert source.count("configure_google_auth(") >= 3  # def + 2 chamadas

    def test_flags_google_existem_no_parser(self, source):
        for flag in (
            "--google-domain",
            "--google-client-id",
            "--google-client-secret",
            "--ui-url",
            "--skip-google-auth",
        ):
            assert flag in source, f"flag {flag} ausente no parser"
