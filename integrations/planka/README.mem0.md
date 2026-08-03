# PLANKA no Mem0 Shared

Código do [PLANKA](https://github.com/plankanban/planka) incorporado em `mem0-shared` para a feature **kanban-planka** (ADR-004 / TechSpec).

## Origem / pin

| Campo | Valor |
|-------|--------|
| Upstream local | `/mnt/Dados/dsv/planka` |
| Versão pin (`package.json`) | **2.1.1** |
| Path canônico | `integrations/planka/` |
| Licença | Fair Use — ver `LICENSE.md` + `LICENSES/` (notices preservados) |

Cópia sem `.git`, `node_modules`, `.env` nem caches grandes.

## Postgres — escolha de schema

**Schema `planka` no mesmo database `openmemory`** (mesmo padrão do AgentRegistry / TechSpec).

- Motivo: um único `pg_dump` cobre Spec + espelho; sem DB extra no PgBouncer.
- Knex usa `searchPath` (`MEM0_PG_SCHEMA`); Sails usa `schemaName` no datastore (`config/datastores.js`).
- Entrypoint `docker/start-mem0.sh` cria o schema e injeta `search_path` no DSN.
- `CREATE SCHEMA` idempotente em `server/mem0/ensure-schema.js` (volumes Postgres já existentes).
- Init opcional em volume vazio: `docker/postgres-init/01-create-planka-schema.sql`.

**Não** usa Qdrant nem o volume `mem0_storage`.

## Auth bridge (fail-closed)

Hook Sails: `server/api/hooks/mem0-auth/`.

Quando `AUTH_JWT_SECRET` está definido, **toda** request `/api/*` precisa de um destes:

| Credencial | Condição |
|------------|----------|
| JWT HS256 | Assinado com `AUTH_JWT_SECRET` (mesmo segredo Mem0 / `NEXTAUTH_SECRET`), claims `sub` + opcionais `email`/`name`/`picture` |
| `Authorization: Bearer local` | Só se `MEM0_AUTH_ALLOW_LEGACY=1` |
| `INTERNAL_ACCESS_TOKEN` | Token interno PLANKA já existente |
| `omtk_*` | Lookup em `public.agent_tokens` (Postgres compartilhado) |

Sem credencial válida → `401` JSON `{ code: "E_MEM0_UNAUTHORIZED" }`.

| Método | `req.currentUser` |
|--------|-------------------|
| JWT UI | Upsert por e-mail (nome/foto/`language=pt-BR`/admin) + membership nos projetos Spec espelhados |
| INTERNAL / legacy / omtk | `DEFAULT_ADMIN` (FK-safe para mirror) |

Se `AUTH_JWT_SECRET` estiver vazio, o bridge é no-op (auth upstream PLANKA apenas).

Helpers testáveis: `server/api/hooks/mem0-auth/lib/validate-auth.js`.

## Product UI (ADR-008)

- Marca na UI: **Kanban** (não “PLANKA”).
- Idioma default: **pt-BR** (`DEFAULT_LANGUAGE` + `language` no upsert Mem0).
- Aba OpenMemory **Kanban** (`/docs`) carrega a home do SPA via `GET /api/v1/specs/kanban-home`.
- Coluna **SDD** em cada quadro (cards PRD / TechSpec / ADRs / Tasks); pipeline Spec à direita.
- Ambiente compartilhado: todo usuário Mem0 vê e edita todos os projetos/quadros (admin + project manager + board editor).
- Spec SoT para agentes; `create_workspace` espelha quadro quando `PLANKA_MIRROR_SYNC=1`.
- Cutover: `POST /admin/planka/resync`; rebuild só `planka` + `openmemory-mcp` + `openmemory-ui` (nunca `down -v` / Qdrant).

## Build

```bash
# Docker (context = este diretório)
docker build -f docker/Dockerfile.mem0.runtime -t mem0/planka:local .

# Testes unitários do bridge (sem Docker)
cd server && npm install && node --test test/unit/mem0-auth.test.js
```

Entrypoint Mem0: `docker/start-mem0.sh` → `ensure-schema.js` → upstream `start.sh`.

## Compose (serviço `planka`)

Definido em `openmemory/docker-compose.scale.yml`:

- `build.context: ../integrations/planka`
- Dockerfile: `docker/Dockerfile.mem0.runtime`
- PostgreSQL direto (`postgres:5432`), schema `planka`
- Volume `planka_attachments` → `/app/data` (anexos; **não** Qdrant)
- `AUTH_JWT_SECRET` ← `NEXTAUTH_SECRET` / `AUTH_JWT_SECRET`
- `DEFAULT_LANGUAGE=pt-BR`
- Healthcheck: `GET http://127.0.0.1:1337/`
- Traefik: `PathPrefix(/planka)` com strip-prefix (+ legacy `/planka-api`)
- `openmemory-mcp`: `PLANKA_BASE_URL` / `PLANKA_INTERNAL_URL` default `http://planka:1337`

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | sim | DSN Postgres (DB `openmemory`) |
| `MEM0_PG_SCHEMA` | não | Default `planka` |
| `SECRET_KEY` | sim | Segredo de sessão PLANKA (compose usa `NEXTAUTH_SECRET`) |
| `AUTH_JWT_SECRET` | sim (produção Mem0) | Fail-closed do bridge |
| `MEM0_AUTH_ALLOW_LEGACY` | não | `1` aceita `Bearer local` (dev/LAN) |
| `INTERNAL_ACCESS_TOKEN` / `PLANKA_INTERNAL_ACCESS_TOKEN` | não | Bearer interno do mirror BFF |
| `BASE_URL` | sim | URL base PLANKA |
| `PLANKA_DEFAULT_ADMIN_*` | não | Seed admin na primeira subida |

Deploy seguro (só o serviço; **nunca** `-v`):

```bash
cd openmemory
export AUTH_JWT_SECRET="${AUTH_JWT_SECRET:-$NEXTAUTH_SECRET}"
export MEM0_AUTH_ALLOW_LEGACY=1
docker compose -f docker-compose.scale.yml up -d --no-deps --build planka
```

Smoke:

```bash
./integrations/planka/scripts/smoke-health.sh
# ou com Traefik:
# PLANKA_URL=http://127.0.0.1:8765/planka-api ./integrations/planka/scripts/smoke-health.sh
```

## Notas

- A UI React do PLANKA é o **canvas** da aba Documentações (ADR-007); shell/trilho SDD ficam no Next.
- Path público: `/planka` (sem strip). Mirror interno: `PLANKA_INTERNAL_URL=http://planka:1337`.
- Backup PostgreSQL (`pg_dump` do DB `openmemory`) inclui o schema `planka`.
- Não commitar `.env` nem secrets neste diretório.
- Fair Use: uso interno da equipe; notices em `LICENSE.md`.
- Runbook cutover/rollback/resync: `openmemory/docs/runbooks/planka-cutover-rollback.md`
- Gate go-live: `openmemory/docs/runbooks/planka-go-live-checklist.md`
- ADR-007: `openmemory/docs/adrs/adr-007-planka-canvas-docs.md`
