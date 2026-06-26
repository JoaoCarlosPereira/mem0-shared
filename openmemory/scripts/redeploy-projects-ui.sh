#!/usr/bin/env bash
# Rebuild API + UI com correções da aba Projetos (dedupe, totais, labels).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec bash "$ROOT/scripts/rebuild-ui-api.sh"
