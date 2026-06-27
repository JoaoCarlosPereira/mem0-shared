#!/usr/bin/env bash
set -euo pipefail

# Para a stack scale SEM apagar volumes (Qdrant/PostgreSQL preservados).
#
#   ./scripts/safe-stack-down.sh
#
# Para parar E APAGAR volumes (destrutivo — exige confirmação explícita):
#
#   CONFIRM_VOLUME_DESTROY=1 ./scripts/safe-stack-down.sh --destroy-volumes

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.scale.yml}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DESTROY=0
for arg in "$@"; do
  case "$arg" in
    --destroy-volumes) DESTROY=1 ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
    *)
      echo "Opção desconhecida: $arg" >&2
      exit 1
      ;;
  esac
done

if [[ "$DESTROY" -eq 1 ]]; then
  if [[ "${CONFIRM_VOLUME_DESTROY:-}" != "1" ]]; then
    echo "ERRO: apagar volumes destrói todas as memórias no Qdrant." >&2
    echo "Para confirmar: CONFIRM_VOLUME_DESTROY=1 $0 --destroy-volumes" >&2
    exit 1
  fi
  echo "Parando stack e REMOVENDO volumes (mem0_storage, mem0_pgdata, ...)..."
  docker compose -f "$COMPOSE_FILE" down -v
else
  echo "Parando stack (volumes preservados — memórias no Qdrant mantidas)..."
  docker compose -f "$COMPOSE_FILE" down
fi

echo "Concluído."
