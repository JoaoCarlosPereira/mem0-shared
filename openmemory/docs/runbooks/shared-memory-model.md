# Shared Memory Model — Runbook

## Overview

OpenMemory is deployed as a **shared memory service** on the LAN
(`openmemory/docker-compose.scale.yml`). All team members write into a single
Qdrant collection and a single PostgreSQL `write_queue`. There is **no per-user
or per-group partitioning** in the vector store: every memory point is globally
addressable by ID, and search results are filtered in memory (or via Qdrant
payload filters) based on `project`, `user_id`, `agent_id`, etc.

This document captures the design rationale, the bugs fixed during the
"shared read bugs" workstream, and the decisions that were made about the
model.

---

## Design Principles

1. **Single shared collection.** All memories live in one Qdrant collection
   (`openmemory`). No per-project or per-group collections.
2. **Project is a payload field, not an isolation boundary.** Memories are
   tagged with `payload["project"]` to enable scoped search, but the field does
   not enforce hard isolation. Any authenticated caller can search across all
   projects; anonymous reach depends entirely on the auth mode (see item 3).
3. **Authentication is enforced at the edge, and its strength depends on
   `AUTH_MODE`.** The read/write routes (including `GET /api/v1/memories/{id}`)
   carry **no per-route auth `Depends`** — protection comes from the
   `AuthMiddleware` (`openmemory/api/app/middleware/team_auth.py`). That
   middleware behaves differently per mode (env `AUTH_MODE`, default `warn` in
   `docker-compose.scale.yml`):
   - `warn` (default): an anonymous request (no credential, or `Bearer local`)
     is **allowed through** with only a log warning (`auth warn: ...`). Explicit
     but invalid credentials still return 401. So `GET /api/v1/memories/{id}`
     **is reachable anonymously** in this mode.
   - `enforce`: the same anonymous/legacy request is rejected with **401
     Unauthorized**, guaranteeing no anonymous read. Explicit invalid
     credentials also return 401.
   **Recommendation:** for a multi-team deployment, run `AUTH_MODE=enforce` so
   anonymous reads are impossible. `warn` is only safe for a single, fully
   trusted LAN.
4. **Deletion is fail-closed.** The `deletion_guard` (see
   `openmemory/api/app/utils/deletion_guard.py`) blocks all `DELETE` and
   `delete_all` calls by default. The guards `MEM0_ALLOW_MEMORY_DELETE` and
   `MEM0_ALLOW_BULK_DELETE` default to `0`.

---

## Bug Fixes

### 1. Project propagation in search results

**Symptom:** When searching with a `project` filter, memories from other
projects were leaking into results because the `project` field was not being
propagated correctly through the search pipeline.

**Root cause:** The search endpoint was reading `payload.get("project")` after
the Qdrant search but the filter was being applied to a different payload key
(or not applied at all in some code paths).

**Fix:** The shared-filter endpoint
(`POST /api/v1/memories/shared-filter`) now explicitly filters on
`payload["project"]` when a `project` parameter is supplied. The
`app_ids` and `category_ids` parameters are **accepted but intentionally
ignored** by `vector_stats` — they exist for API compatibility with the
platform API but have no effect in the shared (non-partitioned) model. This is
documented inline in the code.

### 2. `GET /memories/{id}` is guarded by the edge `AuthMiddleware`

**Symptom:** `GET /api/v1/memories/{id}` had **no per-route auth `Depends`**,
so its protection came solely from the `AuthMiddleware`
(`openmemory/api/app/middleware/team_auth.py`). Under the default
`AUTH_MODE=warn`, an anonymous LAN request was allowed through with only a log
warning — meaning any client on the network could read any memory by ID.

**Fix / behavior:** The middleware intercepts every `/api/v1/memories/*` route
(including `GET /api/v1/memories/{id}`), but its response depends on `AUTH_MODE`
(default `warn` in `docker-compose.scale.yml`):

- `warn`: anonymous requests **pass** (log warning only); an explicit invalid
  credential returns 401. The route is reachable without a session.
- `enforce`: anonymous requests are rejected with **401 Unauthorized** — this is
  the only mode that guarantees no anonymous read.

**Recommendation:** set `AUTH_MODE=enforce` for multi-team deployments. The
shared-model behavior (and the Qdrant fallback for `GET /api/v1/memories/{id}`)
is covered by `openmemory/api/tests/test_shared_memories_regression.py`.

### 3. `vector_stats` explicitly ignores `app_ids` / `category_ids`

**Symptom:** Passing `app_ids` or `category_ids` to the shared-filter endpoint
was causing silent filtering errors or incorrect results.

**Root cause:** The `vector_stats` helper was treating `app_ids` and
`category_ids` as real filter dimensions, even though the shared model has no
such partitioning.

**Fix:** `vector_stats` now **explicitly ignores** `app_ids` and `category_ids`
and documents why in a comment. Passing these fields in a request does not
raise an error; they are simply discarded.

---

## Decision: Shared Model (No Hard Group Isolation)

**Decision:** Keep the shared memory model. Do **not** introduce per-group or
per-user Qdrant collections.

**Rationale:**

- The team is small and trusted; soft scoping via `project` + `user_id`
  payload fields is sufficient.
- Hard isolation would require schema changes, migration of existing points,
  and updates to the search pipeline. The cost/benefit ratio does not justify
  it at the current scale.
- The `write_queue` recovery mechanism depends on a single collection.
- Authentication is the primary access control boundary.

**Residual risks:**

- Any authenticated user can read memories belonging to other users or
  projects. This is acceptable for the current deployment.
- If the team grows or external users are added, re-evaluate and consider
  per-group collections or row-level security in the vector store.

---

## Verification Checklist

After deploying changes to the shared-filter or auth endpoints:

1. Run `pytest openmemory/api/tests/test_shared_memories_regression.py` — all
   tests must pass.
2. Verify `GET /admin/deletion-guard` still returns the expected guard state.
3. Confirm `GET /api/v1/memories/{id}` without a session returns **401 when
   `AUTH_MODE=enforce`** (under the default `warn` it passes with a log
   warning — see Design Principle 3).
4. Confirm `POST /api/v1/memories/shared-filter` with a `project` filter
   returns only matching memories and does not error on `app_ids` /
   `category_ids`.
