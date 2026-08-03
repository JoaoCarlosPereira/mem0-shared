"""Validação da task_03 (loja-interna-skills): serviço agentregistry no Compose.

Parse do YAML de orquestração — sem subir Docker no ambiente de teste.
"""

import pytest

from tests.paths import openmemory_root

yaml = pytest.importorskip("yaml")

ROOT = openmemory_root()
COMPOSE = ROOT / "docker-compose.scale.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def agentregistry(compose):
    services = compose["services"]
    assert "agentregistry" in services, "serviço agentregistry ausente no compose"
    return services["agentregistry"]


def test_agentregistry_build_points_to_integrations(agentregistry):
    build = agentregistry["build"]
    assert build["context"] == "../integrations/agentregistry"
    assert "Dockerfile.mem0" in build["dockerfile"]


def test_agentregistry_uses_postgres_not_qdrant(agentregistry):
    env = agentregistry["environment"]
    joined = "\n".join(f"{k}={v}" for k, v in env.items()) if isinstance(env, dict) else "\n".join(str(e) for e in env)
    assert "DATABASE_URL" in joined or "AGENT_REGISTRY_DATABASE_URL" in joined
    assert "mem0_store" not in joined
    assert "QDRANT" not in joined.upper()
    deps = agentregistry.get("depends_on") or {}
    assert "postgres" in deps
    assert "mem0_store" not in deps


def test_agentregistry_no_docker_sock(agentregistry):
    volumes = agentregistry.get("volumes") or []
    joined = "\n".join(str(v) for v in volumes)
    assert "docker.sock" not in joined
    assert agentregistry.get("privileged") in (None, False)


def test_agentregistry_healthcheck_ping(agentregistry):
    hc = agentregistry["healthcheck"]
    test = " ".join(str(x) for x in hc["test"])
    assert "/v0/ping" in test


def test_agentregistry_auth_env_documented(agentregistry):
    env = agentregistry["environment"]
    assert "AUTH_JWT_SECRET" in env
    assert "MEM0_AUTH_ALLOW_LEGACY" in env
