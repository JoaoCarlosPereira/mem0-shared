#!/usr/bin/env bash
# Rebuild API + UI images so attribution fixes (Criada por / Log de Acesso) take effect.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "Docker não acessível. Adicione seu usuário ao grupo docker ou rode com sudo:" >&2
  echo "  sudo docker compose -f docker-compose.scale.yml build openmemory-mcp openmemory-ui" >&2
  echo "  sudo docker compose -f docker-compose.scale.yml up -d openmemory-mcp openmemory-ui" >&2
  exit 1
fi

echo ">> Rebuilding API and UI..."
docker compose -f docker-compose.scale.yml build openmemory-mcp openmemory-ui

echo ">> Restarting services..."
docker compose -f docker-compose.scale.yml up -d openmemory-mcp openmemory-ui

echo ">> Done. Recarregue http://localhost:3000 (Ctrl+Shift+R)."
