"""Regressões do instalador para falhas vistas no deploy LAN (Docker/Ollama/UI)."""

import importlib.util
from types import SimpleNamespace

import pytest

from tests.paths import openmemory_root

_ROOT = openmemory_root()
_INSTALL_PATH = _ROOT.parent / "install.py"
_spec = importlib.util.spec_from_file_location("install_hardening_under_test", _INSTALL_PATH)
install = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install)


@pytest.fixture
def compose_env(tmp_path):
    return tmp_path / ".env"


class TestStoragePreservesExisting:
    def test_yes_sem_data_dir_mantem_qdrant_storage(self, compose_env):
        install.set_env(compose_env, "QDRANT_STORAGE", "/mnt/Dados/memorias/qdrant")
        result = install.configure_storage_scale(
            None, interactive=False, compose_env=compose_env
        )
        assert install.read_env(compose_env, "QDRANT_STORAGE") == "/mnt/Dados/memorias/qdrant"
        assert result == "/mnt/Dados/memorias"

    def test_sem_existente_usa_volume_nomeado(self, compose_env):
        install.configure_storage_scale(None, interactive=False, compose_env=compose_env)
        assert install.read_env(compose_env, "QDRANT_STORAGE") == "mem0_storage"


class TestOllamaHostDetection:
    def test_inference_uses_host_ollama_from_env(self, compose_env):
        install.set_env(compose_env, "LLM_PROVIDER", "ollama")
        install.set_env(compose_env, "OLLAMA_LLM_URL", "http://host.docker.internal:11434")
        assert install.inference_uses_host_ollama(compose_env) is True

    def test_inference_ignora_api_remota(self, compose_env):
        install.set_env(compose_env, "LLM_PROVIDER", "openai")
        install.set_env(compose_env, "LLM_BASE_URL", "https://api.openai.com/v1")
        assert install.inference_uses_host_ollama(compose_env) is False

    def test_ollama_listening_all_interfaces(self, monkeypatch):
        monkeypatch.setattr(install.shutil, "which", lambda cmd: "/usr/bin/ss" if cmd == "ss" else None)

        class _R:
            stdout = "LISTEN 0 4096 *:11434 *:*\n"

        monkeypatch.setattr(
            install.subprocess, "run",
            lambda *a, **k: _R(),
        )
        assert install.ollama_listening_for_docker() is True

    def test_ollama_listening_localhost_only(self, monkeypatch):
        monkeypatch.setattr(install.shutil, "which", lambda cmd: "/usr/bin/ss" if cmd == "ss" else None)

        class _R:
            stdout = "LISTEN 0 4096 127.0.0.1:11434 0.0.0.0:*\n"

        monkeypatch.setattr(
            install.subprocess, "run",
            lambda *a, **k: _R(),
        )
        assert install.ollama_listening_for_docker() is False


class TestHealthAndUiHelpers:
    def test_parse_health_and_memory_client(self):
        detail = (
            'HTTP 200: {"status":"degraded","checks":{"memory_client":'
            '{"status":"degraded","error":"Failed to connect to Ollama"}}}'
        )
        assert install.memory_client_status(detail) == "degraded"
        assert install.parse_health_payload(detail)["status"] == "degraded"

    def test_ensure_docker_access_ok_quando_usable(self, monkeypatch):
        monkeypatch.setattr(install, "docker_usable", lambda: True)
        args = SimpleNamespace(yes=True)
        install.ensure_docker_access(args, interactive=False)  # não deve die


class TestEntrypointAndRequirements:
    def test_entrypoint_nao_faz_sed_bare_de_identifiers(self):
        src = (_ROOT / "ui" / "entrypoint.sh").read_text(encoding="utf-8")
        assert 's|"${key}"|"${esc}"|g' in src or 's|\\"${key}\\"|\\"${esc}\\"|g' in src
        assert "process.env.0" in src or "bare" in src.lower() or "NEVER sed bare" in src
        # Não deve restar o padrão antigo que quebrava AUTH_UI_REQUIRED=0.
        assert 's|${key}|${value}|g' not in src

    def test_requirements_pin_fastapi_abaixo_de_0_140_5(self):
        req = (_ROOT / "api" / "requirements.txt").read_text(encoding="utf-8")
        assert "fastapi>=0.68.0,<0.140.5" in req


class TestInstallerWiringHardening:
    def test_run_production_valida_ui_e_ollama(self):
        src = _INSTALL_PATH.read_text(encoding="utf-8")
        assert "ensure_ollama_reachable_from_docker(" in src
        assert "wait_for_ui(" in src
        assert "ensure_docker_access(" in src
        assert 'set_env(compose_env, "AUTH_UI_REQUIRED", "0")' in src
