#!/usr/bin/env bash
# Rode a suíte unitária da API OpenMemory (pytest + ruff).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="$ROOT/api"
VENV="${OPENMEMORY_TEST_VENV:-/tmp/om-test-venv}"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"

if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$API/requirements.txt" pyyaml ruff
fi

export OPENAI_API_KEY="${OPENAI_API_KEY:-test-key}"
export PYTHONPATH="$REPO_ROOT"
cd "$API"
"$VENV/bin/ruff" check app tests
exec "$VENV/bin/python" -m pytest tests "$@"
