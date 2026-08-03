# Go-live checklist — Kanban PLANKA (task_07)

Gate de cutover para o espelho Spec → PLANKA. **Spec permanece SoT.**  
Proibido: `docker compose down -v`, apagar `mem0_storage`, habilitar `MEM0_ALLOW_*_DELETE`.

## Pré-requisitos

- [ ] Serviço `planka` healthy (`docker compose -f docker-compose.scale.yml ps`)
- [ ] `PLANKA_MIRROR_SYNC=1` nos serviços API/worker
- [ ] Volume `spec_attachments` e `planka_attachments` presentes (não Qdrant)
- [ ] Backup recente Qdrant/Postgres se for ambiente compartilhado

## Smoke MCP (obrigatório)

Rodar na API:

```bash
cd openmemory/api
python3 -m pytest tests/test_planka_go_live_smoke.py tests/test_mcp_specs_tasks.py -q
```

Critério: **exit 0**. Pipeline coberto: `create_task` → `claim` → status até `concluido` → `write_spec_document`.

## Inventário Spec ↔ espelho

Após resync:

```bash
curl -sS -X POST "$OPENMEMORY_URL/admin/planka/resync" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Gate falha se `mirrored_*` / `planka_*_mapped` < contagens Spec, ou se `errors` ≠ [].  
Utilitário: `assert_inventory_gate` em `app/utils/planka_resync.py`.

## Smoke UI (Documentações)

```bash
cd openmemory/ui
npm test -- --testPathPattern='specsBoard|specsPosition|TaskRichFields|specsApi' --coverage=false
```

Manualmente em `/docs/:project/:workspace`:

- [ ] Coluna SDD com prd/techspec/tasks/adrs e link ADR
- [ ] Claim / drag entre colunas
- [ ] Position persistida (reorder)
- [ ] Campos ricos (label/checklist/due) via FastAPI somente

## Resultado do gate

| Item | Resultado | Data |
|------|----------|------|
| pytest go-live smoke | PASS (`test_planka_go_live_smoke.py` 3 passed) | 2026-08-03 |
| inventário pós-resync | PASS (`assert_inventory_gate` no smoke) | 2026-08-03 |
| UI Jest specs | _rodar no verify_ | 2026-08-03 |
| Go / No-go | Go (testes unitários/smoke) — dry-run compose em ambiente alvo | 2026-08-03 |

Skills `cy-*`: **sem breaking change** (ADR-002) — contratos MCP/API congelados.
