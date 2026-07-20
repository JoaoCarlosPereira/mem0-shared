# Rollout — Espaço Compartilhado de Specs (Tarefas 1–14)

Procedimento **reexecutável e não destrutivo** para instalar/atualizar a feature
de specs em produção. Segue as regras de proteção de dados do `AGENTS.md` (fork
OpenMemory em produção na LAN; histórico de perda de 1000+ memórias).

> **NUNCA**, em nenhuma etapa: `docker compose down -v`, `make down-clean` sem
> confirmação, `docker volume rm mem0_storage`, nem recriar o serviço
> `mem0_store` (Qdrant) sem aviso. Para derrubar, use `make down` ou
> `openmemory/scripts/safe-stack-down.sh`. A migration desta feature é
> **puramente aditiva** (7 tabelas novas), mas trate a stack como sensível.

## Natureza da mudança (por que é seguro)

- **DB:** 1 migration Alembic aditiva (`i4d5e6f7a8b9`) — cria 7 tabelas novas
  (`spec_workspaces`, `spec_documents`, `spec_document_versions`, `task_cards`,
  `task_status_history`, `spec_audit_logs`, `spec_comments`). Não altera nenhuma
  tabela/coluna existente (ADR-004). `downgrade -1` remove só essas 7 tabelas.
- **Qdrant:** collection **nova e dedicada** `openmemory_specs`, provisionada
  lazily no 1º uso; a collection `openmemory` (memórias) não é tocada (ADR-006).
- **API:** router novo `/api/v1/specs/*` + 10 tools MCP novas + 1 worker de
  timeout iniciado no `startup` (junto do `write_worker`). Aditivo.
- **UI:** telas novas em `/admin/specs/*` + dependências `@dnd-kit/*`.

## Cenário A — Instalação nova (ambiente limpo/staging)

```bash
cd openmemory
./scripts/smoke-shared-specs.sh        # build + up + migrate + valida specs REST + Qdrant
# KEEP_UP=1 ./scripts/smoke-shared-specs.sh   # para inspecionar sem derrubar
```
Sucesso = script sai 0: API no ar, rotas `/api/v1/specs/*` registradas, Qdrant ok.

## Cenário B — Atualização de produção (sobre dados reais)

1. **Backup primeiro** (defesa em profundidade):
   ```bash
   curl -fsS -X POST "http://localhost:8765/admin/backup/run"   # MinIO bucket mem0-backups
   ```
2. **Puxar o código** e confirmar a migration presente:
   ```bash
   git pull
   ls openmemory/api/alembic/versions/i4d5e6f7a8b9_add_spec_tables.py
   ```
3. **Rebuild só dos serviços alterados** (não a stack inteira — AGENTS.md):
   ```bash
   cd openmemory
   docker compose build openmemory-mcp openmemory-write-worker
   docker compose up -d openmemory-mcp openmemory-write-worker
   ```
   > Não reinicie/recrie `mem0_store` (Qdrant). Confirme antes o `points_count`
   > em `http://localhost:6333/collections/openmemory`.
4. **Aplicar a migration aditiva**:
   ```bash
   make upgrade      # docker compose exec api alembic upgrade head
   ```
5. **Verificar sem impacto** (contagens antes/depois idênticas):
   ```bash
   ./scripts/smoke-shared-specs-upgrade.sh
   ```
   O script captura `memories/groups/projects/users` + `points_count` da
   collection `openmemory` antes e depois, e **falha** se qualquer valor mudar.
6. **Regressão manual das tools de memória** (via um cliente MCP conectado):
   - `add_memories(text=..., project=...)` → retorna `accepted`.
   - `search_memory(query=..., project=...)` → retorna resultados.
   - `list_memories(project=...)` → lista do projeto.
7. **Liberar** a UI (`/admin/specs`) e as skills migradas
   (`/cy-create-prd`, `/cy-create-techspec`, `/cy-create-tasks`) — ver
   `skills/MCP-MIGRATION-VALIDATION.md` para o checklist das skills.

## Rollback (staging; produção só com confirmação do usuário)

```bash
cd openmemory
make downgrade    # alembic downgrade -1 — remove só as 7 tabelas de specs
```
Não afeta `memories/groups/projects/users` nem a collection `openmemory`.
A collection `openmemory_specs`, se criada, pode ser removida à parte no Qdrant
(não é apagada pelo downgrade da migration).

## Critérios de "pode liberar"

- [ ] `smoke-shared-specs-upgrade.sh` sai 0 (contagens e `points_count`
      idênticos antes/depois).
- [ ] 7 tabelas de specs presentes; `openmemory` intacta.
- [ ] `add_memories`/`search_memory`/`list_memories` sem regressão.
- [ ] Backup recente concluído antes do upgrade.
