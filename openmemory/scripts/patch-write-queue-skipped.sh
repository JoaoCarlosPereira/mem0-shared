#!/usr/bin/env bash
# Aplica status ``skipped`` na fila de escrita (jobs sem memória nova ≠ falha).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${PATCH_SRC:-/tmp/mem0-full/openmemory}"

if [[ ! -d "$SRC/api/app/workers" ]]; then
  echo "Fonte não encontrada: $SRC (defina PATCH_SRC ou clone em /tmp/mem0-full)" >&2
  exit 1
fi

sudo cp -a "$SRC/api/app/models.py" "$ROOT/api/app/models.py"
sudo cp -a "$SRC/api/app/utils/write_queue.py" "$ROOT/api/app/utils/write_queue.py"
sudo cp -a "$SRC/api/app/workers/write_worker.py" "$ROOT/api/app/workers/write_worker.py"
sudo cp -a "$SRC/api/app/schemas.py" "$ROOT/api/app/schemas.py"
sudo cp -a "$SRC/api/app/routers/admin.py" "$ROOT/api/app/routers/admin.py"
sudo cp -a "$SRC/api/alembic/versions/d9e0f1a2b3c4_add_write_queue_skipped_status.py" \
  "$ROOT/api/alembic/versions/"
sudo cp -a "$SRC/api/tests/test_write_worker.py" "$ROOT/api/tests/test_write_worker.py"
sudo cp -a "$SRC/api/tests/test_write_queue.py" "$ROOT/api/tests/test_write_queue.py"
sudo cp -a "$SRC/api/tests/test_admin_dashboard.py" "$ROOT/api/tests/test_admin_dashboard.py"
sudo cp -a "$SRC/ui/types/admin.ts" "$ROOT/ui/types/admin.ts"
sudo cp -a "$SRC/ui/lib/i18n/pt-BR.ts" "$ROOT/ui/lib/i18n/pt-BR.ts"
sudo cp -a "$SRC/ui/components/admin/JobStatusBadge.tsx" "$ROOT/ui/components/admin/JobStatusBadge.tsx"
sudo cp -a "$SRC/ui/app/admin/queues/page.tsx" "$ROOT/ui/app/admin/queues/page.tsx"
sudo cp -a "$SRC/ui/__tests__/app/overview.test.tsx" "$ROOT/ui/__tests__/app/overview.test.tsx"
sudo cp -a "$SRC/ui/__tests__/types/admin.types.test.ts" "$ROOT/ui/__tests__/types/admin.types.test.ts"
sudo cp -a "$SRC/ui/__tests__/hooks/adminApi.test.tsx" "$ROOT/ui/__tests__/hooks/adminApi.test.tsx"
sudo cp -a "$SRC/ui/__tests__/store/adminSlice.test.ts" "$ROOT/ui/__tests__/store/adminSlice.test.ts"

echo "Patch aplicado. Rode: sudo docker exec openmemory_api alembic upgrade head"
echo "Depois rebuild: sudo bash $ROOT/scripts/rebuild-ui-api.sh"
