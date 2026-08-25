# Rollout — Isolamento de quadros Kanban por grupo (kanban-board-group-isolation)

Procedimento **reexecutável e não destrutivo** para liberar o isolamento de
quadros Kanban por grupo em produção. Segue as regras de proteção de dados do
`AGENTS.md` (fork OpenMemory em produção na LAN; histórico de perda de 1000+
memórias).

> **NUNCA**, em nenhuma etapa: `docker compose down -v`, `make down-clean` sem
> confirmação, `docker volume rm mem0_storage`, nem recriar o serviço
> `mem0_store` (Qdrant). Para derrubar, use `make down` ou
> `openmemory/scripts/safe-stack-down.sh`.

## Natureza da mudança (por que é volume-safe)

- **DB:** 1 migration Alembic **aditiva e idempotente**
  (`p1e2f3g4h5i6_add_workspace_group_id`) — adiciona a coluna `group_id` em
  `spec_workspaces` (FK p/ `groups.id`, indexada, nullable) e faz **backfill**
  dos workspaces legados resolvendo `created_by` contra o usuário criador.
  Não cria nem altera nenhuma tabela de memória. O FK só é criado no PostgreSQL
  (SQLite não suporta `ALTER ... ADD CONSTRAINT`), mesmo padrão de
  `g2b3c4d5e6f7`. O backfill é **fail-closed**: linhas ambíguas, sem
  correspondência, ou com criador sem grupo ficam `NULL` (invisíveis para todos),
  nunca caem no grupo `Default`.
- **Qdrant:** **não é tocado.** A collection `openmemory` (memórias) e a
  `openmemory_specs` (busca de specs) permanecem intactas. Nenhum `down -v`,
  nenhuma recriação de `mem0_store`.
- **API:** `SpecWorkspace.group_id` + checagem de grupo em `_assert_access`,
  `_filter_accessible`, `create_workspace`, `get_kanban_board`,
  `search_specs_endpoint` e na emissão de token do embed PLANKA. Aditivo.
- **PLANKA (sidecar):** `get-board-group-ids.js` lê `spec_workspaces.group_id`
  direto (não mais `created_by`); `mem0-auth/index.js` substitui o
  `ensureSharedAccess` de acesso total por **reconciliação por grupo** (cria
  membership só para boards do grupo do usuário e revoga as herdadas do antigo
  "tudo compartilhado"); `validate-auth.js` carrega o claim `group` do JWT.

## Componentes afetados (service-scoped)

Só dois serviços precisam de rebuild + a migration:

| Serviço compose | Por quê |
|-----------------|---------|
| `openmemory-mcp` (container `openmemory_api`) | API/Python: model + auth + migration |
| `planka` (container `openmemory_planka`, profile `sidecars`) | Auth hook + filters JS |

**Não** é necessário rebuild de `openmemory-ui`, workers, Qdrant, Postgres ou
MinIO.

## Pré-requisito — volume-safe

Antes de **qualquer** operação na stack, confirme que o volume de memórias está
intacto:

```bash
curl -fsS "http://localhost:6333/collections/openmemory" | grep -E '"points_count"'
# anote o valor; ele deve ser idêntico no fim
```

## Atualização de produção (sobre dados reais)

1. **Backup primeiro** (defesa em profundidade):
   ```bash
   curl -fsS -X POST "http://localhost:8765/admin/backup/run"   # MinIO bucket mem0-backups
   ```
2. **Puxar o código** e confirmar a migration presente:
   ```bash
   git pull
   ls openmemory/api/alembic/versions/p1e2f3g4h5i6_add_workspace_group_id.py
   ```
3. **Rebuild só dos dois serviços alterados** (não a stack inteira — AGENTS.md):
   ```bash
   cd openmemory
   docker compose -f docker-compose.scale.yml build openmemory-mcp planka
   docker compose -f docker-compose.scale.yml up -d --no-deps openmemory-mcp
   docker compose -f docker-compose.scale.yml --profile sidecars up -d --no-deps planka
   ```
   > Não reinicie/recrie `mem0_store` (Qdrant). `--no-deps` evita subir a stack.
4. **Aplicar a migration aditiva + backfill** (o serviço `openmemory-mcp` é o
   container `openmemory_api`, com `alembic` no `api/`):
   ```bash
   cd openmemory
   docker compose -f docker-compose.scale.yml exec openmemory-mcp \
     bash -lc "cd api && alembic upgrade head"
   ```
   O backfill roda dentro da migration e é idempotente (só preenche `NULL`).
   Confira o revision logo depois:
   ```bash
   docker compose -f docker-compose.scale.yml exec openmemory-mcp \
     bash -lc "cd api && alembic current"
   # deve mostrar p1e2f3g4h5i6 (head)
   ```
5. **Verificar sem impacto** (contagens antes/depois idênticas):
   ```bash
   ./scripts/smoke-shared-specs-upgrade.sh
   ```
   O script captura `memories/groups/projects/users` + `points_count` da
   collection `openmemory` antes e depois e **falha** se qualquer valor mudar.

## Verificação manual (isolamento por grupo)

Com dois usuários não-admin em grupos diferentes (ex.: `tax` e `eng`):

- [ ] Cada home lista **apenas** os quadros do seu próprio grupo (criados
      agora + legados backfilled com sucesso).
- [ ] Deep-link de um quadro **do mesmo grupo** carrega.
- [ ] Deep-link **copiado de outro grupo** é negado (403/404), inclusive para o
      usuário que criou o quadro de outro grupo (admin não tem exceção).
- [ ] Todo quadro legado **sem grupo resolvido** está ausente e inacessível
      para todos (fail-closed).
- [ ] Um usuário que antes tinha membership amplo no PLANKA **perdeu** acesso
      aos boards de outros grupos (reconciliação revogou as herdadas).

## Rollback (só com confirmação do usuário)

```bash
cd openmemory
docker compose -f docker-compose.scale.yml exec openmemory-mcp \
  bash -lc "cd api && alembic downgrade -1"   # remove coluna group_id + índice + FK
```

`downgrade` **não** reverte o backfill em nível de dados além de remover a
coluna; como a mudança é aditiva, as memórias (`memories` e collection
`openmemory`) não são afetadas. Para reverter os serviços, rebuild da tag
anterior de `openmemory-mcp` e `planka` (sem tocar Qdrant/volumes).

## Critérios de "pode liberar"

- [ ] `smoke-shared-specs-upgrade.sh` sai 0 (contagens e `points_count`
      idênticos antes/depois).
- [ ] Migration `p1e2f3g4h5i6` aplicada; `group_id` presente em
      `spec_workspaces`; backfill idempotente.
- [ ] `add_memories`/`search_memory`/`list_memories` sem regressão.
- [ ] Checklist de isolamento por grupo (acima) passa com 2 grupos reais.
- [ ] Backup recente concluído antes do upgrade.
