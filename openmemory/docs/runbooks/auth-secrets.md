# Runbook — Autenticação por equipe e segredos

> Prontidão para produção, task_10/task_11 — ADR-006. Alvo LAN.

## Autenticação por equipe (`AUTH_MODE`)

A API valida um token por equipe na borda. Modos (env `AUTH_MODE`):

| Modo | Comportamento |
|------|---------------|
| `off` | Não valida (compatibilidade total com trust-on-LAN). |
| `warn` | **Default.** Valida e contabiliza/loga ausência/invalidez, mas **não bloqueia** GETs legados. Credencial Bearer **inválida** ⇒ 401. `Bearer local` (shim OAuth) ⇒ legado. |
| `enforce` | Rejeita `401` quando o token é ausente/inválido. |

O cliente envia o token em `X-API-Key: <token>` ou `Authorization: Bearer <token>`.
A equipe resolvida é registrada para auditoria (`team_var`); a atribuição por
hostname (ADR-003) permanece.

### Mutações destrutivas `/admin/*`

Mesmo em `AUTH_MODE=warn`, restore/purge/requeue-done/migration/promote exigem
admin autenticado:

| Credencial | Env |
|------------|-----|
| `X-Admin-Token: …` ou `Authorization: Bearer …` | `ADMIN_TOKEN` |
| Sessão JWT da UI (email opcionalmente allowlisted) | `AUTH_ADMIN_EMAILS` (vírgula; vazio = qualquer sessão válida) |

Recomendado em LAN de produção: `AUTH_MODE=enforce` + `ADMIN_TOKEN` forte.

### UI legado (sem Google)

| Env | Efeito |
|-----|--------|
| `AUTH_UI_REQUIRED=0` | Middleware não força `/login`; login oferece “Continuar sem login”. |
| (vazio) + sem `GOOGLE_CLIENT_ID` | Mesmo comportamento legado (auto-detect). |
| `AUTH_UI_REQUIRED=1` ou Google configurado | UI exige sessão Google. |

No modo legado, o container da UI recebe `ADMIN_TOKEN` (server-only) e o
route handler `/api-proxy` injeta `X-Admin-Token` nas mutações `/admin/*`
quando a requisição chega sem `Authorization` nem `X-Admin-Token`. Assim
Backup / Restore / write-queue admin funcionam sem login Google, sem expor o
segredo no bundle `NEXT_PUBLIC_*`. Com sessão Google, o Bearer da sessão
prevalece e o proxy não sobrescreve.

### CORS

`CORS_ORIGINS` — lista separada por vírgula (ex.: `http://localhost:3000,http://192.168.2.184:3000`).
Sem a variável, a API usa `localhost:3000` / `127.0.0.1:3000` e `NEXTAUTH_URL` se setado.
**Não** use `*` com credentials.

### Governance purge

`MEM0_ALLOW_GOVERNANCE_PURGE=0` (default). Purge/cold-tier no Qdrant só rodam com
esta flag ou com o par `MEM0_ALLOW_MEMORY_DELETE` + `MEM0_ALLOW_BULK_DELETE`.

### Rollout recomendado (sem quebrar clientes)

1. Distribua os tokens às equipes e configure os clientes MCP com o header.
2. Suba em `AUTH_MODE=warn` e acompanhe a métrica `auth_denied_total{mode="warn"}`.
3. Quando `auth_denied_total` zerar (todos os clientes migraram), vire `AUTH_MODE=enforce`.

## Fonte dos tokens (fora do `.env` versionado)

Prioridade de carga (`load_team_tokens`):
1. `AUTH_TOKENS_FILE` — caminho de um secret montado. JSON `{ "<equipe>": "<token>" }` ou linhas `equipe:token`.
2. `AUTH_TOKENS` — inline `equipe1:tok1,equipe2:tok2` (apenas dev).

### Docker secret (produção)

Crie o arquivo de tokens **fora** do repositório e monte como secret:

```yaml
# trecho do compose (não versionar o arquivo de tokens)
secrets:
  team_tokens:
    file: ./secrets/team_tokens.json   # fora do controle de versão

services:
  openmemory-mcp:
    secrets: [team_tokens]
    environment:
      AUTH_MODE: enforce
      AUTH_TOKENS_FILE: /run/secrets/team_tokens
```

O default de `AUTH_TOKENS_FILE` já aponta para `/run/secrets/team_tokens`.

## Limpeza do `.env` versionado

- Nenhum valor sensível (tokens, `S3_SECRET_KEY`, senha do PostgreSQL, `API_KEY`)
  deve permanecer em `.env` versionado. Use Docker secrets ou um `.env` local
  não rastreado (já em `.gitignore`).
- `S3_ACCESS_KEY`/`S3_SECRET_KEY` do MinIO: **obrigatórios** no `.env` (compose
  scale/backup não embutem mais o default `minioadmin`).

## Rate limit (contexto)

Os limites por `(project, hostname)` (task_10) são configuráveis por env:
`RL_SEARCH_PER_MIN` (30), `RL_WRITE_PER_MIN` (60), `RL_BURST` (10),
`RL_BURST_WINDOW` (10). Respostas `429` trazem `Retry-After`.
