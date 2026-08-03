"""Validação da task_01 (kanban-planka): serviço planka no Compose.

Parse do YAML de orquestração — sem subir Docker no ambiente de teste.
"""

import pytest

from tests.paths import openmemory_root

yaml = pytest.importorskip("yaml")

ROOT = openmemory_root()
COMPOSE = ROOT / "docker-compose.scale.yml"
POSTGRES = ROOT / "compose" / "postgres.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def planka(compose):
    services = compose["services"]
    assert "planka" in services, "serviço planka ausente no compose"
    return services["planka"]


def test_planka_build_points_to_integrations(planka):
    build = planka["build"]
    assert build["context"] == "../integrations/planka"
    assert "Dockerfile.mem0" in build["dockerfile"]


def test_planka_uses_postgres_schema_not_qdrant(planka):
    env = planka["environment"]
    joined = (
        "\n".join(f"{k}={v}" for k, v in env.items())
        if isinstance(env, dict)
        else "\n".join(str(e) for e in env)
    )
    assert "DATABASE_URL" in joined
    assert "MEM0_PG_SCHEMA" in joined
    assert "planka" in joined
    assert "mem0_store" not in joined
    assert "QDRANT" not in joined.upper()
    deps = planka.get("depends_on") or {}
    assert "postgres" in deps
    assert "mem0_store" not in deps


def test_planka_attachments_volume_not_mem0_storage(planka, compose):
    volumes = planka.get("volumes") or []
    joined = "\n".join(str(v) for v in volumes)
    assert "planka_attachments" in joined
    assert "mem0_storage" not in joined
    assert "planka_attachments" in (compose.get("volumes") or {})


def test_planka_healthcheck_root(planka):
    hc = planka["healthcheck"]
    test = " ".join(str(x) for x in hc["test"])
    assert "1337" in test


def test_planka_auth_env_documented(planka):
    env = planka["environment"]
    assert "AUTH_JWT_SECRET" in env
    assert "MEM0_AUTH_ALLOW_LEGACY" in env


def test_planka_traefik_path_prefix(planka):
    labels = planka.get("labels") or []
    joined = "\n".join(str(x) for x in labels)
    assert "/planka-api" in joined
    assert "stripprefix" in joined.lower() or "planka-strip" in joined


def test_api_env_has_planka_urls(compose):
    # openmemory-mcp inherits x-api-common; env appears on the service after compose merge.
    # Anchor merge may leave PLANKA_* only in YAML text — assert file content.
    text = COMPOSE.read_text(encoding="utf-8")
    assert "PLANKA_BASE_URL" in text
    assert "PLANKA_INTERNAL_URL" in text
    assert "http://planka:1337" in text


def test_postgres_init_mounts_planka_schema():
    text = POSTGRES.read_text(encoding="utf-8")
    assert "01-create-planka-schema.sql" in text
