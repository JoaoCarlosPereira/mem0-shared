#!/usr/bin/env bash
#
# Bootstrap idempotente para o stack de escala (ADR-006).
#
# Sobe o stack completo em um único comando (sem Python no host):
#   - PostgreSQL + PgBouncer + Redis + Qdrant + Traefik + observability + backup
#   - API/MCP, write-worker e governance-worker (processamento off-peak)
#   - migrations Alembic rodam DENTRO da imagem da API (não exige Python no host)
#   - inferência via Ollama EXTERNO (host/LAN); para Ollama em container use o
#     profile `local-inference`
# Aguarda /health via proxy antes de concluir.
#
# Pré-requisitos no host: docker + docker compose v2 + curl. (Nenhum Python.)
#
# Uso:
#   ./scripts/bootstrap-scale.sh
#   ./scripts/bootstrap-scale.sh --skip-detect    # produção com URLs explícitas no .env
#   ./scripts/bootstrap-scale.sh --skip-auth-setup  # não perguntar sobre login Google
#   ./scripts/bootstrap-scale.sh --migrate-sqlite /path/to/openmemory.db
#   ./scripts/bootstrap-scale.sh --restore-from /path/to/backup.zip  # DR: restaura de um .zip
#
# Ollama externo: por padrão os containers usam http://host.docker.internal:11434.
# Para um Ollama em outra máquina, defina no .env: OLLAMA_LLM_URL, OLLAMA_EMBED_URL,
# LLM_MODEL, EMBEDDER_MODEL (e OLLAMA_PROBE_URL para a sonda do host).
#
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="docker-compose.scale.yml"
PROXY_PORT="${PROXY_PORT:-8765}"
TIMEOUT="${TIMEOUT:-300}"
SKIP_DETECT=0
SKIP_AUTH_SETUP=0
SQLITE_SOURCE=""
RESTORE_FROM=""

while [ $# -gt 0 ]; do
  case "$1" in
    --skip-detect) SKIP_DETECT=1; shift ;;
    --skip-auth-setup) SKIP_AUTH_SETUP=1; shift ;;
    --migrate-sqlite) SQLITE_SOURCE="$2"; shift 2 ;;
    --migrate-sqlite=*) SQLITE_SOURCE="${1#*=}"; shift ;;
    --restore-from) RESTORE_FROM="$2"; shift 2 ;;
    --restore-from=*) RESTORE_FROM="${1#*=}"; shift ;;
    -h|--help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *) echo "Argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

if [ -n "$RESTORE_FROM" ] && [ ! -f "$RESTORE_FROM" ]; then
  echo "ERRO: arquivo de backup não encontrado: $RESTORE_FROM" >&2
  exit 2
fi

echo "==> Verificando pré-requisitos (docker, docker compose v2, curl)..."
command -v docker >/dev/null 2>&1 || { echo "ERRO: Docker não encontrado." >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERRO: Docker Compose v2 não encontrado." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "ERRO: curl não encontrado." >&2; exit 1; }

# O compose declara env_file: api/.env — garante o arquivo (a partir do exemplo)
# para o 'docker compose' não falhar. Preserva um .env já existente.
if [ ! -f api/.env ]; then
  [ -f api/.env.example ] || { echo "ERRO: api/.env.example ausente (rode a partir de openmemory/)." >&2; exit 1; }
  cp api/.env.example api/.env
  echo "==> Criado api/.env a partir do exemplo."
fi

# Os modelos são lidos pelo compose via ${LLM_MODEL}/${EMBEDDER_MODEL}, que são
# interpolados de openmemory/.env (ou do shell) — NÃO de api/.env (o bloco
# environment: do compose tem precedência sobre o env_file). Validamos cedo para
# o stack não subir "pronto" e falhar na primeira escrita por modelo vazio.
get_env() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- ; }
LLM_MODEL_VAL="${LLM_MODEL:-$(get_env LLM_MODEL)}"
EMB_MODEL_VAL="${EMBEDDER_MODEL:-$(get_env EMBEDDER_MODEL)}"
if [ -z "$LLM_MODEL_VAL" ] || [ -z "$EMB_MODEL_VAL" ]; then
  echo "ERRO: defina LLM_MODEL e EMBEDDER_MODEL em openmemory/.env (lidos pelo compose)." >&2
  echo "      Liste os modelos do seu Ollama:  curl -s \${OLLAMA_PROBE_URL:-http://localhost:11434}/api/tags" >&2
  echo "      Ex.:  printf 'LLM_MODEL=llama3.1:8b\\nEMBEDDER_MODEL=nomic-embed-text\\n' >> .env" >&2
  echo "      (Ollama em outra máquina? adicione também OLLAMA_LLM_URL e OLLAMA_EMBED_URL no .env.)" >&2
  exit 1
fi
echo "==> Modelos configurados: LLM=$LLM_MODEL_VAL | embedder=$EMB_MODEL_VAL"

# --- Login Google (feature auth Google, ADR-002) -----------------------------
# Pergunta e grava em openmemory/.env tudo que o login precisa; os segredos de
# sessão (AUTH_JWT_SECRET/NEXTAUTH_SECRET) são gerados automaticamente. Sem a
# configuração o login fica desabilitado (fail-closed) e o fluxo legado por
# hostname segue funcionando — o bootstrap NUNCA bloqueia por isso.
gen_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n'
  else
    head -c 48 /dev/urandom | base64 | tr -d '\n='
  fi
}

set_env_if_missing() { # set_env_if_missing CHAVE VALOR
  if [ -z "$(get_env "$1")" ]; then
    printf '%s=%s\n' "$1" "$2" >> .env
  fi
}

detect_lan_ip() {
  hostname -I 2>/dev/null | awk '{print $1}' || true
}

if [ "$SKIP_AUTH_SETUP" -eq 0 ]; then
  AUTH_DOMAIN_VAL="${AUTH_ALLOWED_DOMAIN:-$(get_env AUTH_ALLOWED_DOMAIN)}"
  GCID_VAL="${GOOGLE_CLIENT_ID:-$(get_env GOOGLE_CLIENT_ID)}"
  GCSECRET_VAL="${GOOGLE_CLIENT_SECRET:-$(get_env GOOGLE_CLIENT_SECRET)}"
  if [ -n "$AUTH_DOMAIN_VAL" ] && [ -n "$GCID_VAL" ] && [ -n "$GCSECRET_VAL" ]; then
    # Configuração presente: garante apenas os derivados (idempotente).
    set_env_if_missing AUTH_JWT_SECRET "$(gen_secret)"
    set_env_if_missing NEXTAUTH_SECRET "$(gen_secret)"
    LAN_IP="$(detect_lan_ip)"
    set_env_if_missing NEXTAUTH_URL "http://${LAN_IP:-localhost}:3000"
    echo "==> Login Google configurado (domínio: ${AUTH_DOMAIN_VAL})."
  elif [ -t 0 ]; then
    echo
    echo "==> Login Google (opcional) — identifica pessoas em vez de máquinas."
    echo "    Pré-requisito: credencial OAuth do tipo 'TVs e dispositivos de entrada"
    echo "    limitada' no Google Cloud Console (device flow — sem URL de redirect)."
    echo "    Deixe o domínio em branco para pular (o fluxo legado segue ativo)."
    read -r -p "    Domínio Google Workspace (ex.: sysmo.com.br): " AUTH_DOMAIN_IN
    if [ -n "$AUTH_DOMAIN_IN" ]; then
      read -r -p "    GOOGLE_CLIENT_ID: " GCID_IN
      read -r -s -p "    GOOGLE_CLIENT_SECRET (não é exibido): " GCSECRET_IN
      echo
      LAN_IP="$(detect_lan_ip)"
      DEFAULT_UI_URL="http://${LAN_IP:-localhost}:3000"
      read -r -p "    URL da UI na LAN [${DEFAULT_UI_URL}]: " UI_URL_IN
      UI_URL_IN="${UI_URL_IN:-$DEFAULT_UI_URL}"
      if [ -z "$GCID_IN" ] || [ -z "$GCSECRET_IN" ]; then
        echo "    ! Client ID/Secret ausentes — login Google NÃO configurado."
      else
        set_env_if_missing AUTH_ALLOWED_DOMAIN "$AUTH_DOMAIN_IN"
        set_env_if_missing GOOGLE_CLIENT_ID "$GCID_IN"
        set_env_if_missing GOOGLE_CLIENT_SECRET "$GCSECRET_IN"
        set_env_if_missing NEXTAUTH_URL "$UI_URL_IN"
        set_env_if_missing AUTH_JWT_SECRET "$(gen_secret)"
        set_env_if_missing NEXTAUTH_SECRET "$(gen_secret)"
        echo "    Login Google configurado em openmemory/.env."
        echo "    Device flow: sem URL de redirect (credencial tipo 'TVs e"
        echo "    dispositivos de entrada limitada')."
        echo "    (Opcional, fluxo com redirect futuro: origem ${UI_URL_IN} |"
        echo "     redirect ${UI_URL_IN}/api/auth/callback/google)"
      fi
    else
      echo "    Pulado — configure depois no openmemory/.env (ver api/.env.example)."
    fi
  else
    echo "==> Login Google não configurado (sem TTY) — fluxo legado segue ativo."
    echo "    Defina AUTH_ALLOWED_DOMAIN, GOOGLE_CLIENT_ID/SECRET e NEXTAUTH_URL"
    echo "    no openmemory/.env (ver api/.env.example) e re-rode o bootstrap."
  fi
fi

echo "==> Subindo infraestrutura base (PostgreSQL, PgBouncer, Redis, Qdrant)..."
docker compose -f "$COMPOSE_FILE" up -d postgres pgbouncer redis mem0_store

echo "==> Aguardando PgBouncer..."
for _ in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" exec -T pgbouncer pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Construindo a imagem da API..."
docker compose -f "$COMPOSE_FILE" build openmemory-mcp

echo "==> Rodando migrations em container (alembic upgrade head)..."
# Sem dependência de Python no host: o alembic roda dentro da imagem da API,
# que já o contém. O DATABASE_URL vem do compose (aponta para pgbouncer na rede
# interna). --no-deps: a infra base já está de pé.
docker compose -f "$COMPOSE_FILE" run --rm --no-deps openmemory-mcp alembic upgrade head

if [ -n "$SQLITE_SOURCE" ]; then
  echo "==> Migração guiada SQLite -> PostgreSQL (requer python3 no host)..."
  python3 scripts/migrate_sqlite_to_postgres.py "$SQLITE_SOURCE"
fi

# Restore opcional de desastre (ADR-004): aplica um .zip ANTES de liberar a stack
# de aplicação, em container one-shot (mesmo padrão do alembic upgrade). Sem a
# flag, a instalação segue normal (stack vazia). O snapshot de segurança NÃO se
# aplica aqui (ambiente novo) — ver app/scripts/restore_backup.py.
if [ -n "$RESTORE_FROM" ]; then
  echo "==> Restaurando estado a partir de ${RESTORE_FROM} (one-shot)..."
  docker compose -f "$COMPOSE_FILE" run --rm --no-deps \
    -v "$(realpath "$RESTORE_FROM"):/restore/backup.zip:ro" \
    openmemory-mcp python -m app.scripts.restore_backup /restore/backup.zip
fi

if [ "$SKIP_DETECT" -eq 0 ] && [ -z "${OLLAMA_EMBED_URL:-}" ] && [ -z "${EMBEDDER_BASE_URL:-}" ]; then
  # Sonda o Ollama externo (host/LAN) via curl — sem Python no host. Do host, um
  # Ollama no próprio servidor responde em localhost:11434; ajuste OLLAMA_PROBE_URL
  # para um Ollama em outra máquina.
  PROBE_URL="${OLLAMA_PROBE_URL:-http://localhost:11434}"
  echo "==> Verificando Ollama externo em ${PROBE_URL} ..."
  if curl -fsS "${PROBE_URL%/}/api/tags" >/tmp/om_tags.json 2>/dev/null; then
    echo "    Ollama respondeu. Modelos disponíveis:"
    grep -oE '"model"[[:space:]]*:[[:space:]]*"[^"]+"' /tmp/om_tags.json \
      | sed -E 's/.*"([^"]+)"$/      - \1/' || true
    echo "    Confirme que LLM_MODEL e EMBEDDER_MODEL no .env apontam para modelos acima."
  else
    echo "    ! Ollama não respondeu em ${PROBE_URL}."
    echo "      Defina OLLAMA_LLM_URL/OLLAMA_EMBED_URL e LLM_MODEL/EMBEDDER_MODEL no .env"
    echo "      (Ollama no host usa http://host.docker.internal:11434 de dentro dos containers)."
  fi
fi

echo "==> Subindo stack completo..."
docker compose -f "$COMPOSE_FILE" up -d --build

echo "==> Aguardando /health via proxy (timeout ${TIMEOUT}s)..."
deadline=$((SECONDS + TIMEOUT))
until curl -sf "http://localhost:${PROXY_PORT}/health" | grep -q '"status"'; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERRO: /health não respondeu a tempo." >&2
    exit 1
  fi
  sleep 3
done

echo "==> Stack pronto."
echo "    Proxy MCP:  http://localhost:${PROXY_PORT}/discovery"
echo "    Prometheus: http://localhost:${PROMETHEUS_PORT:-9090}"
echo "    Grafana:    http://localhost:${GRAFANA_PORT:-3001}"
echo
echo "    Governança (off-peak) roda no serviço openmemory-governance-worker."
echo "    Logs:   docker compose -f ${COMPOSE_FILE} logs -f openmemory-governance-worker"
echo "    Forçar um job agora (fura o curfew): "
echo "      curl -X POST http://localhost:${PROXY_PORT}/admin/governance/jobs/dedup -d '{\"project\":\"<project>\"}'"
