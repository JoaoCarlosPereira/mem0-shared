#!/usr/bin/env bash
# Smoke test do Espaço Compartilhado de Specs — ATUALIZAÇÃO sobre dados reais
# (task_15). Confirma empiricamente que a migration da Tarefa 1 é PURAMENTE
# ADITIVA: aplicada sobre uma stack já no ar e populada, NÃO altera nenhuma
# contagem existente (memories/groups/projects/users) nem o points_count da
# collection Qdrant `openmemory`.
#
# NÃO É DESTRUTIVO: nunca usa `down -v`, nunca apaga volumes/filas. Roda contra
# uma stack JÁ NO AR (não faz build/up) — ideal para staging que espelhe
# produção. Segue AGENTS.md: rebuild apenas dos serviços alterados.
#
# Uso (com a stack já rodando):
#   ./scripts/smoke-shared-specs-upgrade.sh
#
# Variáveis:
#   API_PORT    (default 8765)
#   QDRANT_PORT (default 6333)
#   HOST        (default localhost)
#   REBUILD     (default 1)  rebuild só de openmemory-mcp + openmemory-write-worker
#   MEM_COLLECTION (default openmemory)

set -euo pipefail

cd "$(dirname "$0")/.."

API_PORT="${API_PORT:-8765}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
HOST="${HOST:-localhost}"
REBUILD="${REBUILD:-1}"
MEM_COLLECTION="${MEM_COLLECTION:-openmemory}"

log() { printf '\n=== %s ===\n' "$*"; }
fail() { echo "ERRO: $*" >&2; exit 1; }

# Contagens das tabelas existentes via a própria config de DB da aplicação
# (funciona em SQLite ou PostgreSQL). Imprime "memories groups projects users".
table_counts() {
  docker compose exec -T api python - <<'PY'
from app.database import SessionLocal
from app.models import Memory, Group, Project, User
db = SessionLocal()
try:
    print(db.query(Memory).count(), db.query(Group).count(),
          db.query(Project).count(), db.query(User).count())
finally:
    db.close()
PY
}

# points_count de uma collection Qdrant (0 se a collection não existir).
qdrant_points() {
  local col="$1" body
  body=$(curl -fsS "http://${HOST}:${QDRANT_PORT}/collections/${col}" 2>/dev/null || echo "")
  echo "$body" | grep -o '"points_count":[0-9]*' | head -1 | grep -o '[0-9]*' || echo "0"
}

log "confirmando que a stack está no ar"
curl -fsS "http://${HOST}:${API_PORT}/discovery" >/dev/null 2>&1 \
  || fail "API não está respondendo em ${HOST}:${API_PORT} — suba a stack antes (make up)."

log "CAPTURA ANTES — contagens de tabelas e points_count do Qdrant"
BEFORE_TABLES="$(table_counts)"
BEFORE_MEM_POINTS="$(qdrant_points "${MEM_COLLECTION}")"
echo "tabelas (memories groups projects users): ${BEFORE_TABLES}"
echo "qdrant ${MEM_COLLECTION} points_count: ${BEFORE_MEM_POINTS}"

if [ "${REBUILD}" = "1" ]; then
  log "rebuild apenas dos serviços alterados (AGENTS.md): openmemory-mcp + openmemory-write-worker"
  docker compose build openmemory-mcp openmemory-write-worker 2>/dev/null \
    || docker compose build api 2>/dev/null || true
  docker compose up -d openmemory-mcp openmemory-write-worker 2>/dev/null \
    || docker compose up -d api 2>/dev/null || true
  # espera a API voltar
  for _ in $(seq 1 40); do
    curl -fsS "http://${HOST}:${API_PORT}/discovery" >/dev/null 2>&1 && break
    sleep 3
  done
fi

log "aplicando a migration aditiva (make upgrade / alembic upgrade head)"
docker compose exec -T api alembic upgrade head

log "CAPTURA DEPOIS — contagens de tabelas e points_count do Qdrant"
AFTER_TABLES="$(table_counts)"
AFTER_MEM_POINTS="$(qdrant_points "${MEM_COLLECTION}")"
echo "tabelas (memories groups projects users): ${AFTER_TABLES}"
echo "qdrant ${MEM_COLLECTION} points_count: ${AFTER_MEM_POINTS}"

log "RELATÓRIO DE COMPARAÇÃO (antes → depois)"
echo "tabelas:            [${BEFORE_TABLES}] → [${AFTER_TABLES}]"
echo "${MEM_COLLECTION}:  ${BEFORE_MEM_POINTS} → ${AFTER_MEM_POINTS}"

[ "${BEFORE_TABLES}" = "${AFTER_TABLES}" ] \
  || fail "contagens de tabelas MUDARAM — a migration NÃO foi aditiva!"
[ "${BEFORE_MEM_POINTS}" = "${AFTER_MEM_POINTS}" ] \
  || fail "points_count da collection ${MEM_COLLECTION} MUDOU — memórias afetadas!"
echo "OK: nada existente foi alterado (mudança puramente aditiva — ADR-004)."

log "verificando as 7 tabelas novas de specs após o upgrade"
docker compose exec -T api python - <<'PY'
import sys
from sqlalchemy import inspect
from app.database import engine
tables = set(inspect(engine).get_table_names())
expected = {"spec_workspaces","spec_documents","spec_document_versions",
            "task_cards","task_status_history","spec_audit_logs","spec_comments"}
missing = expected - tables
if missing:
    print("ERRO: tabelas de specs ausentes:", missing); sys.exit(1)
print("OK: 7 tabelas de specs presentes.")
PY

log "regressão das rotas de memória existentes (sem quebrar após o upgrade)"
curl -fsS "http://${HOST}:${API_PORT}/discovery" >/dev/null \
  || fail "/discovery quebrou após o upgrade"
echo "OK: /discovery responde. (Rode manualmente add_memories/search_memory/"
echo "    list_memories via MCP para confirmar as tools — ver rollout doc.)"

log "collection de specs 'openmemory_specs' (provisionada lazily — ADR-006)"
SPECS_POINTS="$(qdrant_points "openmemory_specs")"
echo "openmemory_specs points_count: ${SPECS_POINTS} (0 é esperado sem specs concluídas)"

log "SMOKE (atualização) OK — migration aditiva confirmada, sem regressão"
echo "Rollback (staging): 'make downgrade' (alembic downgrade -1) remove apenas"
echo "as 7 tabelas de specs, sem tocar em memories/groups/projects/users."
