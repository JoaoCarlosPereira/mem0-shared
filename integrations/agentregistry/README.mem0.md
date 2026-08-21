# AgentRegistry no ShareMem

Código do [AgentRegistry](https://github.com/agentregistry-dev/agentregistry) incorporado em `sharemem` para a feature **loja-interna-skills** (ADR-003 / ADR-007).

## Origem

- Cópia de trabalho a partir de `/mnt/Dados/dsv/agentregistry` (sem `.git` aninhado, sem `node_modules` / `.env`).
- Path canônico neste monorepo: `integrations/agentregistry/`.

## Build

```bash
# Local (requer Go 1.26+)
go build -o bin/server ./cmd/server

# Docker (context = este diretório)
docker build -f docker/server.Dockerfile -t mem0-agentregistry:local .
```

Entrypoint Mem0 (Authn/AuthZ fail-closed):

```bash
go build -o bin/mem0registry ./cmd/mem0registry
# Requer AUTH_JWT_SECRET; opcional AUTH_ADMIN_EMAILS, MEM0_AUTH_ALLOW_LEGACY=1
# omtk_ usa AGENT_REGISTRY_DATABASE_URL ou DATABASE_URL (schema public.agent_tokens)
```

## Compose (serviço `agentregistry`)

Definido em `openmemory/docker-compose.scale.yml`:

- `build.context: ../integrations/agentregistry`
- Imagem runtime: `docker/Dockerfile.mem0.runtime` (binário pré-compilado em `docker/artifacts/mem0registry`)
- Entrypoint: `mem0registry`
- PostgreSQL compartilhado (conexão **direta** ao host `postgres`, não PgBouncer), schema `agentregistry`
- Traefik: `PathPrefix(/registry-api)` com strip-prefix
- Healthcheck: `GET /v0/ping`
- Sem volume Qdrant / sem `docker.sock`

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `AGENT_REGISTRY_DATABASE_URL` / `DATABASE_URL` | sim | DSN Postgres (migrações + schema `agentregistry`) |
| `AUTH_JWT_SECRET` | sim | Segredo HS256 ShareMem (pode espelhar `NEXTAUTH_SECRET`) |
| `AUTH_ADMIN_EMAILS` | não | E-mails admin (CSV) |
| `MEM0_AUTH_ALLOW_LEGACY` | não | `1` aceita `Authorization: Bearer local` (dev/LAN) |
| `AGENT_REGISTRY_SERVER_ADDRESS` | não | Default `:8080` |
| `AGENT_REGISTRY_MCP_PORT` | não | `0` desliga MCP embutido do registry |
| `AGENT_REGISTRY_LOG_LEVEL` | não | `info` |

Deploy seguro (só o serviço; **nunca** `-v`):

```bash
cd openmemory
# se AUTH_JWT_SECRET não estiver no .env:
export AUTH_JWT_SECRET="$NEXTAUTH_SECRET"
export MEM0_AUTH_ALLOW_LEGACY=1
docker compose -f docker-compose.scale.yml up -d --no-deps agentregistry
```

## Seed do catálogo Mem0

O seed versionado publica as skills locais de `skills/*/` como recursos
`Skill` no AgentRegistry e envia o diretório completo como artefato
`tar+gzip`. O pacote inclui `SKILL.md`, referências, scripts e demais arquivos,
sem depender de repositório Git; a UI oferece o download equivalente em ZIP.

```bash
python3 integrations/agentregistry/scripts/seed-mem0-skills.py \
  --registry-url http://127.0.0.1:8765/registry-api \
  --token local
```

Para validar contra o registry sem mutar:

```bash
python3 integrations/agentregistry/scripts/seed-mem0-skills.py \
  --registry-url http://127.0.0.1:8765/registry-api \
  --token local \
  --dry-run
```

Para apenas inspecionar o YAML gerado:

```bash
python3 integrations/agentregistry/scripts/seed-mem0-skills.py --print-yaml
```

E2E local opcional (publish → discover → install em tmpdir; não toca home real):

```bash
cd openmemory/api
RUN_STORE_E2E=1 \
STORE_E2E_REGISTRY_URL=http://127.0.0.1:8765/registry-api \
STORE_E2E_TOKEN=local \
pytest tests/test_store_seed_e2e.py
```

## Notas

- UI Next do registry permanece no tree para referência; a experiência da equipe é a UI OpenMemory `/store`.
- Backup PostgreSQL (`pg_dump`) inclui o schema `agentregistry` automaticamente — ver `openmemory/docs/runbooks/backup-restore.md`.
- Não commitar `.env` nem secrets neste diretório.
- Binário em `docker/artifacts/` e `bin/` é artefato local (não versionar se pesado).
