"""Cloud-compatible ``/v3/memories`` shim for the local-only plugin hooks.

Why this exists:
  The official mem0 plugin's lifecycle hooks speak the cloud Platform REST
  contract (``POST /v3/memories/search/``, ``/v3/memories/add/`` and
  ``POST /v3/memories/`` for listing/counting). To run those hooks fully
  local — with zero cloud egress — the only thing the plugin changes is its
  base URL (see ``integrations/mem0-plugin/scripts/_endpoints.py``). This
  router implements the same paths the hooks call, backed by the local memory
  client, so no hook needs to learn a new contract.

Scope model (task_03 / ADR-003): semantic search is GLOBAL across projects and
SHARED across the team. ``user_id`` in incoming filters is attribution only and is
intentionally NOT used to restrict reads. The ``app_id`` field the hooks send is a
soft ranking hint (small boost for matching project names); relevance + recency
dominate ordering. List/count endpoints remain project-scoped.

Reads reuse the same vector-store path as ``app.mcp_server.search_memory``.
Writes call ``memory_client.add`` directly (not the async write queue) so the
hook-supplied ``metadata`` — ``type``, ``file``, etc. — is preserved, which the
typed hook searches depend on. The token in ``Authorization: Token <x>`` is
accepted and ignored (the local server is trust-on-LAN; auth is out of scope).
"""

import logging
from typing import Any, Optional

from app.utils.groups import ensure_user_registered, requester_group_for_mcp
from app.utils.memory import get_memory_client
from app.utils.partitioning import bind_active_collection
from app.utils.read_audit import record_memory_reads
from app.utils.recency import rank_search_results
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/v3/memories", tags=["compat"])

# Keep parity with app.mcp_server read-path defaults.
DEFAULT_TOP_K = 20
MAX_TOP_K = 100


def _memory_client():
    try:
        return get_memory_client()
    except Exception as e:  # noqa: BLE001
        logging.warning("compat_v3: memory client unavailable: %s", e)
        return None


def _walk_clauses(filters: Any):
    """Yield each leaf clause dict from a cloud-style AND/OR filter tree."""
    if isinstance(filters, dict):
        for key in ("AND", "OR"):
            if key in filters and isinstance(filters[key], list):
                for clause in filters[key]:
                    yield from _walk_clauses(clause)
                return
        yield filters
    elif isinstance(filters, list):
        for clause in filters:
            yield from _walk_clauses(clause)


def _extract_scope(filters: Any) -> tuple[Optional[str], dict, bool, Optional[str]]:
    """Return (project, metadata_filters, is_global, requester_hostname).

    ``project`` comes from an ``app_id`` clause. ``metadata_filters`` collects
    any ``{"metadata": {...}}`` clauses for Python-side post-filtering. A
    ``{"user_id": "*"}`` clause flags a global (cross-project) read.
    ``requester_hostname`` is the first concrete ``user_id`` (hostname) in filters,
    used to resolve the reader's group from ``users.group_id`` — not for filtering.
    """
    project: Optional[str] = None
    metadata_filters: dict = {}
    is_global = False
    requester_hostname: Optional[str] = None
    for clause in _walk_clauses(filters):
        if not isinstance(clause, dict):
            continue
        if clause.get("app_id"):
            project = str(clause["app_id"])
        uid = clause.get("user_id")
        if uid == "*":
            is_global = True
        elif uid and requester_hostname is None:
            requester_hostname = str(uid)
        meta = clause.get("metadata")
        if isinstance(meta, dict):
            metadata_filters.update(meta)
    return project, metadata_filters, is_global, requester_hostname


def _payload_matches_metadata(payload: dict, wanted: dict) -> bool:
    """True if every wanted metadata key matches the stored payload.

    mem0 flattens custom metadata into the vector-store payload top level
    (that is how the ``project`` filter works), but we also check a nested
    ``metadata`` dict defensively in case a backend nests it.
    """
    nested = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for key, value in wanted.items():
        if payload.get(key) == value or nested.get(key) == value:
            continue
        return False
    return True


def _hit_to_result(h) -> dict:
    payload = getattr(h, "payload", {}) or {}
    return {
        "id": getattr(h, "id", None),
        "memory": payload.get("data"),
        "score": getattr(h, "score", None),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "project": payload.get("project"),
        "owner": payload.get("hostname"),
        "metadata": payload,
    }


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
class SearchRequest(BaseModel):
    query: str = ""
    filters: Any = None
    top_k: int = DEFAULT_TOP_K
    threshold: float = 0.0
    rerank: bool = False


@router.post("/search/")
async def search(request: SearchRequest, http_request: Request) -> dict:
    """Semantic search across all projects, ranked by relevance and recency."""
    client = _memory_client()
    if not client or not request.query:
        return {"results": []}

    project, metadata_filters, is_global, requester_hostname = _extract_scope(request.filters)
    preferred_project = None if is_global else project

    # Grupo do solicitante: user_id nos filters (plugin) ou header legado → users.group_id.
    reader_host = requester_hostname or http_request.headers.get("x-openmemory-host")
    requester_group = requester_group_for_mcp(reader_host)

    bind_active_collection(client)

    top_k = max(1, min(request.top_k or DEFAULT_TOP_K, MAX_TOP_K))
    # Over-fetch when we have to post-filter by metadata so the caller still
    # gets up to top_k matches after filtering.
    fetch_k = min(MAX_TOP_K, top_k * 4) if metadata_filters else top_k

    hits = None
    degraded = None
    try:
        embeddings = client.embedding_model.embed(request.query, "search")
        hits = client.vector_store.search(
            query=request.query,
            vectors=embeddings,
            top_k=fetch_k,
            filters=None,
            shard_key_selector=None,
        )
    except Exception as e:  # noqa: BLE001
        logging.warning("compat_v3 semantic search failed (%s); falling back to list", e)
        degraded = "list_fallback"
        try:
            raw = client.vector_store.list(filters=None, top_k=fetch_k)
            if isinstance(raw, (tuple, list)) and raw and isinstance(raw[0], (list, tuple)):
                hits = raw[0]
            else:
                hits = raw
        except Exception as list_err:  # noqa: BLE001
            logging.exception("compat_v3 list fallback failed: %s", list_err)
            return {"results": []}

    results = []
    for h in hits or []:
        payload = getattr(h, "payload", {}) or {}
        if metadata_filters and not _payload_matches_metadata(payload, metadata_filters):
            continue
        score = getattr(h, "score", None)
        if request.threshold and score is not None and score < request.threshold:
            continue
        results.append(_hit_to_result(h))

    # Order by semantic relevance blended with recency, THEN truncate to top_k, so
    # a recently-updated fact can win over a more-similar but stale one even when it
    # sat below top_k by raw score (ADR-003 at read time; parity with
    # app.mcp_server.search_memory). The `rerank` arg is kept for backward
    # compatibility but no longer gates ordering; set MEM0_SEARCH_RECENCY_WEIGHT=0
    # for pure semantic order.
    rank_search_results(
        results, preferred_project=preferred_project, requester_group=requester_group
    )
    results = results[:top_k]

    record_memory_reads(
        project=project,
        memory_ids=[r.get("id") for r in results],
        access_type="search",
        source="compat_v3",
        query=request.query,
        items=results,
    )

    out: dict = {"results": results}
    if degraded:
        out["degraded"] = degraded
    return out


# --------------------------------------------------------------------------- #
# Add
# --------------------------------------------------------------------------- #
class AddRequest(BaseModel):
    messages: Optional[list] = None
    text: Optional[str] = None
    user_id: Optional[str] = None
    app_id: Optional[str] = None
    metadata: dict = {}
    infer: bool = True


def _messages_to_text(messages: Optional[list], text: Optional[str]) -> str:
    if text:
        return text
    if not messages:
        return ""
    parts = []
    for m in messages:
        if isinstance(m, dict):
            content = m.get("content", "")
            role = m.get("role", "")
            parts.append(f"{role}: {content}" if role else str(content))
        else:
            parts.append(str(m))
    return "\n".join(p for p in parts if p).strip()


@router.post("/add/")
async def add(request: AddRequest) -> dict:
    """Add a memory scoped by project, preserving hook-supplied metadata."""
    client = _memory_client()
    if not client:
        return {"status": "unavailable", "results": []}

    text = _messages_to_text(request.messages, request.text)
    if not text:
        return {"status": "empty", "results": []}

    project = request.app_id or "default"
    metadata = dict(request.metadata or {})
    metadata.setdefault("project", project)
    metadata.setdefault("source_app", "openmemory")

    ensure_user_registered(request.user_id)

    # Writes target the active collection (blue-green, ADR-003).
    bind_active_collection(client)

    try:
        result = client.add(
            text,
            user_id=request.user_id or "openmemory",
            project=project,
            metadata=metadata,
            infer=request.infer,
        )
    except Exception as e:  # noqa: BLE001
        logging.exception("compat_v3 add failed: %s", e)
        return {"status": "error", "error": str(e), "results": []}

    results = result.get("results", []) if isinstance(result, dict) else []
    return {"status": "ok", "event_id": (results[0].get("id") if results else None),
            "results": results}


# --------------------------------------------------------------------------- #
# List / count
# --------------------------------------------------------------------------- #
class ListRequest(BaseModel):
    filters: Any = None


@router.post("/")
async def list_memories(request: Request, body: ListRequest) -> dict:
    """List/count project-scoped memories (used by session start + timeline)."""
    client = _memory_client()
    if not client:
        return {"count": 0, "results": []}

    project, metadata_filters, is_global, requester_hostname = _extract_scope(body.filters)
    vs_filters: dict = {} if is_global else {"project": project} if project else {}

    reader_host = requester_hostname or request.headers.get("x-openmemory-host")
    requester_group = requester_group_for_mcp(reader_host)

    # List scans the active collection with the project filter (ADR-003).
    bind_active_collection(client)

    try:
        page_size = int(request.query_params.get("page_size", DEFAULT_TOP_K))
    except (TypeError, ValueError):
        page_size = DEFAULT_TOP_K
    page_size = max(1, min(page_size, MAX_TOP_K))

    try:
        raw = client.vector_store.list(filters=vs_filters or None, top_k=MAX_TOP_K)
    except Exception as e:  # noqa: BLE001
        logging.exception("compat_v3 list failed: %s", e)
        return {"count": 0, "results": []}

    points = raw
    if isinstance(raw, (tuple, list)) and raw and isinstance(raw[0], (list, tuple)):
        points = raw[0]

    results = []
    for p in points or []:
        payload = getattr(p, "payload", {}) or {}
        if metadata_filters and not _payload_matches_metadata(payload, metadata_filters):
            continue
        results.append({
            "id": getattr(p, "id", None),
            "memory": payload.get("data"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "owner": payload.get("hostname"),
            "metadata": payload,
        })

    rank_search_results(
        results,
        preferred_project=None if is_global else project,
        requester_group=requester_group,
    )

    count = len(results)
    page_results = results[:page_size]

    record_memory_reads(
        project=project,
        memory_ids=[r.get("id") for r in page_results],
        access_type="list",
        source="compat_v3",
        items=page_results,
    )

    return {"count": count, "results": page_results}
