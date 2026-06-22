#!/usr/bin/env bash
# Aplica fix do botão Excluir (useMemoriesApi.ts é root-owned no host).
set -euo pipefail
FILE="$(cd "$(dirname "$0")/.." && pwd)/ui/hooks/useMemoriesApi.ts"
python3 - "$FILE" << 'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text()
old = '''      await axios.delete(`${getApiUrl()}/api/v1/memories/`, {
        data: { memory_ids, user_id }
      });'''
new = '''      await axios.post(`${getApiUrl()}/api/v1/memories/actions/delete`, {
        memory_ids,
        user_id,
      });'''
if old not in text:
    if 'actions/delete' in text:
        print('already patched')
        sys.exit(0)
    print('pattern not found', file=sys.stderr)
    sys.exit(1)
p.write_text(text.replace(old, new))
print('patched', p)
PY
