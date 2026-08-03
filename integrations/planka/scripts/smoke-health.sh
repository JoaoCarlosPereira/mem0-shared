#!/usr/bin/env bash
# Smoke: PLANKA health + fail-closed auth bridge.
# Usage:
#   ./integrations/planka/scripts/smoke-health.sh
#   PLANKA_URL=http://127.0.0.1:8765/planka-api ./integrations/planka/scripts/smoke-health.sh
set -euo pipefail

PLANKA_URL="${PLANKA_URL:-http://127.0.0.1:1337}"
# Strip trailing slash
PLANKA_URL="${PLANKA_URL%/}"

echo "==> GET ${PLANKA_URL}/ (health)"
code="$(curl -sS -o /tmp/planka-smoke-body.txt -w '%{http_code}' --max-time 10 "${PLANKA_URL}/" || true)"
if [[ "${code}" != "200" ]]; then
  echo "FAIL: expected HTTP 200 from /, got ${code}"
  cat /tmp/planka-smoke-body.txt 2>/dev/null || true
  exit 1
fi
echo "OK health (${code})"

echo "==> GET ${PLANKA_URL}/api/users (expect 401 without auth when bridge enabled)"
api_code="$(curl -sS -o /tmp/planka-smoke-api.txt -w '%{http_code}' --max-time 10 "${PLANKA_URL}/api/users" || true)"
if [[ "${api_code}" != "401" && "${api_code}" != "403" ]]; then
  # Bridge disabled (no AUTH_JWT_SECRET) still returns 401 from PLANKA is-authenticated.
  if [[ "${api_code}" == "200" ]]; then
    echo "FAIL: /api/users returned 200 without credentials (fail-closed broken)"
    cat /tmp/planka-smoke-api.txt
    exit 1
  fi
fi
echo "OK unauthenticated API rejected (${api_code})"

if [[ -n "${PLANKA_SMOKE_TOKEN:-}" ]]; then
  echo "==> GET ${PLANKA_URL}/api/users with Bearer token"
  auth_code="$(curl -sS -o /tmp/planka-smoke-auth.txt -w '%{http_code}' --max-time 10 \
    -H "Authorization: Bearer ${PLANKA_SMOKE_TOKEN}" \
    "${PLANKA_URL}/api/users" || true)"
  echo "Authenticated /api/users → HTTP ${auth_code}"
  if [[ "${auth_code}" == "401" ]]; then
    echo "FAIL: token rejected"
    cat /tmp/planka-smoke-auth.txt
    exit 1
  fi
fi

echo "smoke-health: PASS"
