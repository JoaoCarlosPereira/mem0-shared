"""Validação da task_10 (feature auth Google): envs/secrets no compose e
ausência de vazamento de ?token= em access logs (ADR-003).

Mesmo padrão de ``test_docker_stack_backup.py``: parse dos YAMLs de
orquestração sem depender de Docker no ambiente de teste.
"""

import pytest

from tests.paths import openmemory_root

yaml = pytest.importorskip("yaml")

ROOT = openmemory_root()
COMPOSE = ROOT / "docker-compose.scale.yml"
PROXY = ROOT / "compose" / "proxy.yml"
ENV_EXAMPLE = ROOT / "api" / ".env.example"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def proxy():
    return yaml.safe_load(PROXY.read_text(encoding="utf-8"))


# -- envs da API (bloco x-api-env compartilhado) -----------------------------
def test_api_env_has_google_auth_vars(compose):
    env = compose["x-api-common"]["environment"]
    # GOOGLE_CLIENT_SECRET na API: exigido pelo polling do Device Flow (ADR-007).
    for key in (
        "AUTH_JWT_SECRET",
        "AUTH_ALLOWED_DOMAIN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    ):
        assert key in env, f"faltando {key} no x-api-env"


def test_api_env_defaults_are_fail_closed(compose):
    env = compose["x-api-common"]["environment"]
    # Sem valor no .env, o default é vazio => login Google desabilitado
    # (fail-closed), nunca um segredo embutido no repositório.
    assert env["AUTH_JWT_SECRET"] == "${AUTH_JWT_SECRET:-}"
    assert env["AUTH_ALLOWED_DOMAIN"] == "${AUTH_ALLOWED_DOMAIN:-}"


# -- envs da UI (NextAuth) ---------------------------------------------------
def test_ui_service_has_nextauth_vars(compose):
    env_list = compose["services"]["openmemory-ui"]["environment"]
    joined = "\n".join(str(e) for e in env_list)
    for key in (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "NEXTAUTH_SECRET",
        "NEXTAUTH_URL",
    ):
        assert key in joined, f"faltando {key} no serviço openmemory-ui"


def test_ui_secrets_never_hardcoded(compose):
    env_list = compose["services"]["openmemory-ui"]["environment"]
    joined = "\n".join(str(e) for e in env_list)
    assert "GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET:-}" in joined
    assert "NEXTAUTH_SECRET=${NEXTAUTH_SECRET:-}" in joined


# -- vazamento de ?token= em access logs (ADR-003) ---------------------------
def test_api_uvicorn_access_log_disabled(compose):
    command = str(compose["services"]["openmemory-mcp"]["command"])
    assert "--no-access-log" in command, (
        "o access log do uvicorn imprime a URL com ?token= — deve ficar "
        "desabilitado (ADR-003)"
    )


def test_traefik_access_log_not_enabled(proxy):
    command = [str(c) for c in proxy["services"]["traefik"]["command"]]
    enabled = [c for c in command if c.startswith("--accesslog") and "=true" in c]
    if enabled:
        # Se algum dia for habilitado, o RequestPath (que carrega ?token=)
        # precisa ser dropado.
        assert any("RequestPath=drop" in c for c in command), (
            "access log do Traefik habilitado sem drop do RequestPath "
            "(vaza ?token= — ADR-003)"
        )


# -- HTTPS da UI via Traefik (ADR-009) ----------------------------------------
def test_traefik_tem_entrypoint_websecure_e_porta_443(proxy):
    command = [str(c) for c in proxy["services"]["traefik"]["command"]]
    assert any("--entrypoints.websecure.address=:443" in c for c in command)
    ports = [str(p) for p in proxy["services"]["traefik"]["ports"]]
    assert any(":443" in p for p in ports)


def test_traefik_monta_config_tls_e_certs(proxy):
    volumes = [str(v) for v in proxy["services"]["traefik"]["volumes"]]
    assert any("traefik/tls.yml" in v for v in volumes)
    assert any("/certs" in v for v in volumes)
    tls = yaml.safe_load((ROOT / "compose" / "traefik" / "tls.yml").read_text(encoding="utf-8"))
    certs = tls["tls"]["certificates"][0]
    assert certs["certFile"].startswith("/certs/")
    assert certs["keyFile"].startswith("/certs/")


def test_ui_roteada_por_hostname_no_websecure(compose):
    labels = [str(l) for l in compose["services"]["openmemory-ui"]["labels"]]
    joined = "\n".join(labels)
    assert "traefik.enable=true" in joined
    assert "UI_HOSTNAME" in joined and "Host(" in joined
    assert "entrypoints=websecure" in joined
    assert "tls=true" in joined
    assert "loadbalancer.server.port=3000" in joined


def test_traefik_nao_disputa_443_por_padrao(proxy):
    # A porta TLS default é 8443 (host já tem proxy na 443) — evita conflito.
    ports = [str(p) for p in proxy["services"]["traefik"]["ports"]]
    tls_map = [p for p in ports if p.endswith(":443")]
    assert tls_map and "8443" in tls_map[0], (
        "default do PROXY_TLS_PORT deve ser 8443 para não conflitar com o proxy da empresa"
    )


def test_ui_expoe_mcp_url_para_comandos_de_instalacao(compose):
    # Sem NEXT_PUBLIC_MCP_URL, comandos MCP sairiam com hostname:8765 (quebrado)
    # quando a UI é acessada por hostname — a var fixa o IP:8765 real.
    env_list = compose["services"]["openmemory-ui"]["environment"]
    joined = "\n".join(str(e) for e in env_list)
    assert "NEXT_PUBLIC_MCP_URL" in joined


def test_api_env_tem_client_dedicado_do_device_flow(compose):
    env = compose["x-api-common"]["environment"]
    assert "GOOGLE_DEVICE_CLIENT_ID" in env
    assert "GOOGLE_DEVICE_CLIENT_SECRET" in env


def test_certs_dir_nunca_versiona_chaves():
    gitignore = (ROOT / "certs" / ".gitignore").read_text(encoding="utf-8")
    assert "*" in gitignore.splitlines()


# -- guarda CRITICAL: nada de mexer nos dados --------------------------------
def test_qdrant_volume_unchanged(compose):
    qdrant_vols = compose["services"]["mem0_store"]["volumes"]
    assert any(
        "mem0_storage" in str(v) and "/qdrant/storage" in str(v)
        for v in qdrant_vols
    )


# -- documentação de deploy ---------------------------------------------------
def test_env_example_documents_auth_vars_and_migration():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in (
        "AUTH_JWT_SECRET",
        "AUTH_ALLOWED_DOMAIN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "NEXTAUTH_SECRET",
        "NEXTAUTH_URL",
    ):
        assert key in text, f".env.example deve documentar {key}"
    assert "alembic upgrade head" in text, (
        ".env.example deve documentar o passo manual de migração do deploy"
    )
