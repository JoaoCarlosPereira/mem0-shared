#!/usr/bin/env bash
# Consultas de memória isentas de rate limit + fallback list quando embed falha.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sudo python3 "$ROOT/scripts/patch-critical-reads.py"
echo "Patch aplicado. Rode: sudo bash $ROOT/scripts/rebuild-ui-api.sh"
