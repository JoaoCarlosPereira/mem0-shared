#!/usr/bin/env bash
# Smoke test do Espaço Compartilhado de Specs — INSTALAÇÃO NOVA (task_15).
#
# Sobe a stack em um ambiente LIMPO (make build/up + migrate), espera a API e o
# Qdrant, e confirma que os novos endpoints /api/v1/specs/* estão registrados e
# respondendo. Operação 100% local. NÃO é destrutivo: nunca usa `down -v`.
#
# ATENÇÃO (AGENTS.md): este script NÃO deve ser rodado contra a stack de
# produção com dados reais para o cenário "instalação nova" — use um ambiente
# limpo/staging. Para o cenário de ATUALIZAÇÃO sobre dados reais, use
# scripts/smoke-shared-specs-upgrade.sh.
#
# Uso:
#   ./scripts/smoke-shared-specs.sh            # sobe, valida e derruba (sem -v)
#   KEEP_UP=1 ./scripts/smoke-shared-specs.sh  # sobe e valida, sem derrubar
#
# Variáveis:
#   API_PORT    (default 8765)   porta da API/MCP
#   QDRANT_PORT (default 6333)   porta do Qdrant
#   HOST        (default localhost)
#   TIMEOUT     (default 120)    segundos de espera pela API

set -euo pipefail

cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8765}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
HOST="${HOST:-localhost}"
TIMEOUT="${TIMEOUT:-120}"

log() { printf '\n=== %s ===\n' "$*"; }

cleanup() {
  if [ "${KEEP_UP:-0}" != "1" ]; then
    # NUNCA `down -v` — preserva volumes (AGENTS.md).
    log "derrubando o conjunto (preservando volumes)"
    docker compose down
  else
    log "KEEP_UP=1: deixando os containers no ar"
  fi
}
trap cleanup EXIT

log "build da stack (docker compose build)"
docker compose build

log "subindo a stack (docker compose up -d)"
docker compose up -d

log "aguardando GET /discovery responder 200 (até ${TIMEOUT}s)"
deadline=$(( SECONDS + TIMEOUT ))
until curl -fsS "http://${HOST}:${API_PORT}/discovery" >/dev/null 2>&1; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "ERRO: /discovery não respondeu em ${TIMEOUT}s" >&2
    docker compose logs --tail=50 openmemory-mcp >&2 || true
    exit 1
  fi
  sleep 3
done
echo "OK: API no ar."

log "aplicando migrations (alembic upgrade head)"
docker compose exec -T api alembic upgrade head

# Uma rota registrada retorna qualquer código EXCETO 404. Aceitamos
# 200/401/403/422 (existe, mas pode exigir auth/parâmetros); rejeitamos 404.
assert_route_exists() {
  local method="$1" path="$2" ; shift 2
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "http://${HOST}:${API_PORT}${path}" "$@" || true)
  if [ "$code" = "404" ]; then
    echo "ERRO: rota ausente (404): ${method} ${path}" >&2
    exit 1
  fi
  echo "OK: rota registrada (${code}): ${method} ${path}"
}

log "validando que os endpoints /api/v1/specs/* estão registrados"
assert_route_exists GET  "/api/v1/specs/projects/smoke-proj/workspaces"
assert_route_exists GET  "/api/v1/specs/search?q=teste"
assert_route_exists POST "/api/v1/specs/workspaces" \
  -H "Content-Type: application/json" \
  -d '{"project_id":"smoke-proj","slug":"smoke-ws","name":"Smoke WS"}'

log "conferindo o Qdrant (porta ${QDRANT_PORT})"
if ! curl -fsS "http://${HOST}:${QDRANT_PORT}/readyz" >/dev/null 2>&1 \
   && ! curl -fsS "http://${HOST}:${QDRANT_PORT}/" >/dev/null 2>&1; then
  echo "ERRO: Qdrant não respondeu na porta ${QDRANT_PORT}" >&2
  exit 1
fi
echo "OK: Qdrant respondendo."

log "SMOKE (instalação nova) OK — specs REST + migration + Qdrant no ar"
echo "Nota: a collection 'openmemory_specs' é provisionada lazily no 1º uso"
echo "      (indexação de uma spec concluída ou 1ª busca) — ADR-006."
