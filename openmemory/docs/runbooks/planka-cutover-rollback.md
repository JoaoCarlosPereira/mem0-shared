# Runbook: Cutover / Rollback / Resync — Kanban PLANKA

Documento operacional do cutover único Spec → espelho PLANKA (ADR-003/004/005/006).  
**Spec permanece fonte de verdade.** O sidecar PLANKA é projeção síncrona.

## HARD RULES (memórias)

| Proibido | Usar em vez disso |
|----------|-------------------|
| `docker compose down -v` | `openmemory/scripts/safe-stack-down.sh` / `make down` |
| `docker volume rm mem0_storage` | — |
| Recriar `mem0_store` sem aviso | Verificar `points_count` em Qdrant antes |
| `MEM0_ALLOW_MEMORY_DELETE=1` / bulk delete | Só com pedido explícito do usuário |
| Restaurar backup Qdrant às cegas | `POST /admin/backup/restore` só com confirmação |

Volumes de anexos Kanban (`spec_attachments`, `planka_attachments`) **não** são Qdrant.

## Pré-cutover

1. Backup Postgres + Qdrant (política usual / `POST /admin/backup/run`).
2. Confirmar pin vendor: `integrations/planka/` + notices em `LICENSE.md` / `LICENSES/`.
3. Subir sidecar sem derrubar stack:

```bash
cd openmemory
docker compose -f docker-compose.scale.yml up -d --no-deps --build planka
docker compose -f docker-compose.scale.yml ps planka
```

4. Garantir env nos serviços API (`openmemory-mcp` / workers):

- `PLANKA_BASE_URL=http://planka:1337`
- `PLANKA_MIRROR_SYNC=1`
- `SPEC_ATTACHMENTS_DIR=/mnt/spec-attachments`
- Token interno alinhado (`PLANKA_INTERNAL_ACCESS_TOKEN` / `INTERNAL_ACCESS_TOKEN`)

5. Rebuild **somente** API/worker se necessário (não a stack inteira / não `mem0_store`):

```bash
docker compose -f docker-compose.scale.yml up -d --no-deps --build openmemory-mcp openmemory-write-worker
```

6. Rodar gate smoke: ver [`planka-go-live-checklist.md`](./planka-go-live-checklist.md).

## Cutover (único)

1. Migrar schema Spec (Alembic até head, inclui `m8b9c0d1e2f3` campos ricos + `l7a8b9c0d1e2` id_map).
2. Bootstrap do espelho:

```bash
curl -sS -X POST "$OPENMEMORY_URL/admin/planka/resync" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Opcional por workspace: `{"workspace_id":"<uuid>"}`.

3. Validar inventário no JSON de resposta (`totals` + `errors` vazio). Gate: `assert_inventory_gate`.
4. Manter UI Documentações em `/docs/...` (só FastAPI). Sem iframe PLANKA no browser.
5. Smoke MCP: create → claim → status → write_document (checklist go-live).

## Pós-cutover / monitoramento

Sinais úteis:

- Health PLANKA / Traefik `/planka-api`
- Taxa de HTTP 502 com `mirror_failed: true` nas mutações Spec
- Latência Spec vs mirror (logs `planka_mirror_failed`, `action=...`)
- Contagens `spec_planka_id_map` vs `task_cards` / `spec_documents`
- Idade do último resync bem-sucedido

Alertas sugeridos:

- PLANKA healthcheck down
- `mirror_failed` rate acima do limiar
- Divergência inventário Spec vs id_map

## Resync (recuperação)

Idempotente via `spec_planka_id_map`. **Nunca apaga Spec.**

```bash
# Workspace único
curl -sS -X POST "$OPENMEMORY_URL/admin/planka/resync" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"<uuid>"}'
```

Se o sidecar ficou inconsistente: reinicie **apenas** `planka` (`--no-deps`), depois resync. Não toque em `mem0_store`.

## Rollback operacional (sem destruição de memória)

Objetivo: voltar a operar só com Spec (como antes do espelho), **sem** apagar volumes de memória.

1. Desligar sync: `PLANKA_MIRROR_SYNC=0` nos serviços API/worker e redeploy desses serviços.
2. Opcional: parar o container `planka` (`docker compose stop planka`) — schema Spec e UI `/docs` continuam.
3. **Não** dropar tabelas Spec; **não** `down -v`; **não** apagar `mem0_pgdata` / `mem0_storage`.
4. Dados Spec (cards, docs, campos ricos) permanecem; o espelho pode ser reconstruído depois com resync.

## Checklist Fair Use / licença

Vendor em `integrations/planka/`:

- [x] `LICENSE.md` presente
- [x] `LICENSES/` com Community + Commercial + License Guide (EN/DE)
- [x] `README.mem0.md` descreve uso Mem0 / patches

Uso neste fork:

- [ ] Uso **interno** na LAN (equipe) — não oferecer PLANKA como SaaS a terceiros sob o vendor Fair Use
- [ ] Notices preservados em updates do pin de versão
- [ ] Documentar qualquer patch Mem0 (auth bridge, Dockerfile.mem0.runtime) no README.mem0.md

## Referências

- ADRs do workspace `kanban-planka` (Shared)
- Compose: `openmemory/docker-compose.scale.yml` (serviço `planka`, volumes anexos)
- Código: `app/utils/planka.py`, `planka_hooks.py`, `planka_resync.py`
- Gate: `docs/runbooks/planka-go-live-checklist.md`
