# ShareMem — Shared Memory for AI Engineering Agents

**ShareMem** is a local-first, team-shared memory layer for AI engineering agents
(Claude Code, Cursor, Codex, and MCP clients). One install on your LAN gives every
agent the same long-lived project memory — decisions, conventions, bugs fixed,
and durable learnings — without sending content to the cloud.

> Product name: **ShareMem** · Tagline: *Shared Memory for AI Engineering Agents*  
> Runtime surface: OpenMemory (API/MCP + UI) · Vector store: Qdrant · LLM: Ollama / llama.cpp

## Why ShareMem exists

Engineering teams that run AI agents lose context constantly: every session starts
cold, every machine has its own scratchpad, and team knowledge never accumulates.
Cloud memory products solve the sharing problem by sending proprietary code,
business rules, and secrets off-network — which is a non-starter for many orgs.

ShareMem’s objective is simple:

**One shared, private memory for the whole team — scoped by `project`, readable and
writable by any agent on any host, running 100% on your LAN, and ready to scale
from a laptop to hundreds of millions of memories.**

Concrete target: ~200 developers and dozens of MCP agents on self-hosted infra.

## Design principles

| Principle | What we do | Why |
|-----------|------------|-----|
| **Local-first, fail-closed** | Server **refuses to start** if LLM/embedder points at a non-local host (`MEM0_LOCAL_ONLY=1`); telemetry off. | Privacy is enforced in code, not convention. |
| **Scope by `project`, not machine** | Memories are keyed by `project`; hostname is for attribution/audit only. | Any agent on any host sees the same project store. |
| **Async writes, immediate ack** | `add_memories` enqueues and returns `{queued, job_id}`; a worker extracts via LLM later. | Agents must not block on slow extraction. |
| **Separate read and write paths** | Search/embedding on the API path; LLM extraction on dedicated workers. | Fast, frequent reads don’t fight heavy batch writes. |
| **Partition by tenant** | Collection/shard routing by `project`; huge projects can get a dedicated collection. | Keeps each index small and search fast at scale. |
| **Quality governance** | Reversible quarantine, TTL, dedup, semantic consolidation, per-project caps, cold tier. | Volume without lifecycle pollutes retrieval. |
| **Operate with confidence** | CI gate, backup/restore, end-to-end tracing, rate limits, team auth. | Demo-ready ≠ production-ready. |

## What you get today

All planned phases are **done** and covered by
tests (`openmemory/api`: **375 passed, 2 skipped**).

| Capability | Highlights |
|------------|------------|
| **Shared memory** | `project`-scoped store; MCP tools; discovery + provision; local model detection (Ollama / llama.cpp) |
| **Async write path** | Durable queue (SQLite or PostgreSQL); write worker with retries; fire-and-forget ack |
| **Scale stack** | PostgreSQL + PgBouncer, Redis cache, Traefik edge, separate write workers, `/health` + `/metrics` |
| **Qdrant partitioning** | Tenant routing; promote large projects; blue/green migration admin |
| **Governance** | `active` / `quarantined` / `purged`; TTL; dedup; consolidate; quota; cold tier |
| **Production readiness (LAN)** | CI gate, MinIO/S3 backup+restore, OpenTelemetry, per-`(project, hostname)` rate limit, team auth |

**Out of scope (by design for LAN):** multi-node Qdrant cluster, HPA/K8s migration,
one collection per project by default, dedicated GPU TEI/vLLM, mTLS between
services, optional hybrid search. Resilience without a cluster is covered by
**backup/restore** (single-node). See [ADR-001](.docs/tasks/prontidao-producao/adrs/adr-001.md).

## Deploy profiles

| Profile | When | Compose / script | DB | Workers |
|---------|------|------------------|----|---------|
| **Local-first** | Dev / small team / one machine | `python install.py` → `openmemory/docker-compose.yml` | SQLite | Embedded write worker |
| **Scale (Compose)** | LAN, dozens of agents | `openmemory/scripts/bootstrap-scale.sh` → `docker-compose.scale.yml` | PostgreSQL + PgBouncer | API replicas + write-worker; migration via `--profile migration` |
| **Scale (Swarm)** | Explicit replicas | `docker stack deploy -c docker-stack.yml mem0` | PostgreSQL + PgBouncer | API ×4, write-worker ×8, governance-worker ×1 |

> Governance worker ships in `docker-stack.yml`. On Compose scale, run manually:
> `python -m app.workers.governance_worker` with the same env as the API.

## Architecture (one sentence)

Shared memory **per `project`**: each fact becomes a **vector** in Qdrant; **writes
are async** (durable queue → worker → LLM extract); **reads are sync and fast**
(semantic search + cache); **governance** runs off-peak to keep quality. Nothing
leaves the LAN.

```
Agents (Claude Code, Cursor, Codex, …)
        │  MCP  /mcp/{client_name}/sse/{hostname}
        ▼
┌─────────────────────────────┐
│ openmemory-mcp  (API/MCP)   │  :8765
│  write queue + fail-closed  │
└──────────┬──────────────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
Qdrant          Local LLM
(:6333)         Ollama / llama.cpp
```

Scale mode adds Traefik, Redis, PostgreSQL/PgBouncer, and dedicated write /
governance / migration workers. Full diagrams and data-flow:
[`openmemory/docs/self-hosted-scale-architecture.md`](openmemory/docs/self-hosted-scale-architecture.md).

### Critical data protection

Team memories live in Docker volume **`mem0_storage` (Qdrant)** and the durable
**`write_queue` (PostgreSQL)**. Losing the Qdrant volume has already cost 1000+
memories; recovery depends on the Postgres queue.

- Never `docker compose down -v` — use `openmemory/scripts/safe-stack-down.sh`
- Deletion is fail-closed (`MEM0_ALLOW_MEMORY_DELETE` / `MEM0_ALLOW_BULK_DELETE` default `0`)
- Details: [`AGENTS.md`](AGENTS.md) (CRITICAL section)

## Quick start (local-first)

**Prerequisites:** Docker + Compose v2, Python 3.8+, and a local LLM
(Ollama and/or llama.cpp) reachable on the network.

```bash
python install.py
```

Useful flags:

```bash
python install.py --ollama-url http://192.168.0.10:11434
python install.py --backend llamacpp --llamacpp-url http://192.168.0.10:8080
python install.py --llm llama3.1:latest --embedder nomic-embed-text --yes
python install.py --data-dir /srv/mem0-data --with-ui
```

Services: `mem0_store` (Qdrant `:6333`), `openmemory-mcp` (`:8765`), optional UI (`:3000`).

> Do **not** use upstream `openmemory/run.sh` — it expects `OPENAI_API_KEY`.
> Use `install.py` / `openmemory/install-local-first.sh`.

Guide: [`openmemory/INSTALL-memoria-compartilhada.md`](openmemory/INSTALL-memoria-compartilhada.md).

### Scale bootstrap

```bash
cd openmemory
./scripts/bootstrap-scale.sh
docker compose -f docker-compose.scale.yml up -d
```

### Smoke test

```bash
cd openmemory
./scripts/smoke-memoria-compartilhada.sh
KEEP_UP=1 ./scripts/smoke-memoria-compartilhada.sh
```

## Connect an agent

With the server up (`:8765`), point an agent at `/provision` so it can install MCP
config and memory mode settings.

**Cursor example** (replace `SERVIDOR`):

```
Leia http://SERVIDOR:8765/provision?host=cursor e execute a receita retornada:
escreva o bloco MCP no arquivo indicado, defina as variáveis de ambiente do
campo "env", apresente as 3 opções de modo de memória e grave a escolha em
~/.mem0/settings.json. Confirme cada ação com o usuário antes de executar.
```

Same pattern for `host=claude-code` and `host=codex`.

### MCP tools

| Tool | Role |
|------|------|
| `add_memories(text, project)` | Async enqueue; immediate accept ack |
| `search_memory(query, project)` | Semantic search over **active** project memories |
| `list_memories(project)` | List (includes quarantined — ops/admin) |
| `delete_memories(memory_ids)` | Delete by ID (blocked unless delete guard enabled) |
| `delete_all_memories()` | Bulk delete (blocked unless bulk guard enabled) |

`project` is **required** on read/write tools. It defines the shared space.

### Agent memory modes (`~/.mem0/settings.json`)

| Mode | Behavior |
|------|----------|
| **1. Read + write** | Auto search + capture |
| **2. Read; manual write** | Auto context; write on request (recommended default) |
| **3. Manual** | Everything via `/mem0:*` and MCP |

## Ops cheat sheet

| Endpoint | Use |
|----------|-----|
| `GET /discovery` | MCP auto-config |
| `GET /provision` | Agent install recipe |
| `GET /health` / `GET /metrics` | Health + Prometheus |
| `POST /admin/backup/{run,restore}` | Backup / restore (Qdrant + Postgres → MinIO/S3) |
| `GET/PUT /admin/governance/policies` | Global governance policy |
| `POST /admin/governance/jobs/{job_type}` | Enqueue governance job |
| `POST /admin/migration/*` | Partition migration control |
| `POST /admin/projects/{name}/promote` | Promote project to dedicated collection |
| `GET /admin/deletion-guard` | Deletion guard status |

Essential env: `MEM0_LOCAL_ONLY=1`, `MEM0_TELEMETRY=false`, LLM/embedder URLs,
`DATABASE_URL`, `REDIS_URL` (scale), `AUTH_MODE`, backup S3 settings.
See `openmemory/api/.env.example`.

## Tests

```bash
cd openmemory/api && pytest tests/
pytest tests/memory/test_project_scope.py tests/vector_stores/test_qdrant.py
```

Same suite runs in CI (`ci-gate.yml` → `openmemory-api-ci.yml`).

## Internal docs

| Path | Content |
|------|---------|
| [`.docs/tasks/`](.docs/tasks/) | PRD / TechSpec / ADRs for all phases |
| [`openmemory/docs/runbooks/`](openmemory/docs/runbooks/) | Backup, auth, governance, incident |
| [`openmemory/INSTALL-memoria-compartilhada.md`](openmemory/INSTALL-memoria-compartilhada.md) | Local-first install |
| [`openmemory/docs/self-hosted-scale-architecture.md`](openmemory/docs/self-hosted-scale-architecture.md) | Target architecture + implementation status |
| [`AGENTS.md`](AGENTS.md) | Contributor / agent guide for this monorepo |

## Technology foundation

ShareMem’s product and ops surface are the OpenMemory platform and the local-first
shared-memory stack in this repo. Under the hood it still uses the open-source
**mem0** SDK packages (`mem0/`, vector stores, etc.) as a library foundation —
extended with `project` scope, governance filters, durable queues, and LAN
fail-closed guards.

Upstream mem0 docs (SDK reference only): https://docs.mem0.ai

## License

Apache 2.0 — see [LICENSE](LICENSE).
