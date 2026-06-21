"""Qdrant-backed memory counts and listing for the admin dashboard and shared UI.

MCP writes land in the vector store (indexed by ``project``), not in the SQL
``memories`` table. These helpers read the live collection so counts and lists
match what operators see via MCP.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _vector_store():
    from app.utils.memory import get_memory_client_safe
    from app.utils.partitioning import bind_active_collection

    client = get_memory_client_safe()
    if client is None:
        return None, None
    bind_active_collection(client)
    return client, client.vector_store


def count_collection_memories() -> int:
    """Total points in the active Qdrant collection."""
    _, vs = _vector_store()
    if vs is None:
        return 0
    try:
        return vs.client.count(collection_name=vs.collection_name, exact=True).count
    except Exception:  # noqa: BLE001
        logger.exception("failed to count collection memories")
        return 0


def count_project_memories(project: str) -> int:
    """Count points for a single project via the tenant ``project`` payload field."""
    _, vs = _vector_store()
    if vs is None:
        return 0
    try:
        filt = vs._create_filter({"project": project})
        return vs.client.count(
            collection_name=vs.collection_name,
            count_filter=filt,
            exact=True,
        ).count
    except Exception:  # noqa: BLE001
        logger.exception("failed to count memories for project %s", project)
        return 0


def count_memories_last_24h() -> int:
    """Approximate count of points created in the last 24 hours (scroll sample)."""
    _, vs = _vector_store()
    if vs is None:
        return 0
    cutoff = datetime.now(UTC).timestamp() - 86400
    count = 0
    offset = None
    try:
        while True:
            records, offset = vs.client.scroll(
                collection_name=vs.collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for rec in records or []:
                payload = getattr(rec, "payload", {}) or {}
                created = payload.get("created_at")
                if not created:
                    continue
                try:
                    ts = datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    continue
                if ts >= cutoff:
                    count += 1
            if offset is None:
                break
    except Exception:  # noqa: BLE001
        logger.exception("failed to count recent memories")
    return count


def list_shared_memories(
    *,
    search: Optional[str] = None,
    project: Optional[str] = None,
    page: int = 1,
    size: int = 10,
    sort_direction: str = "desc",
) -> dict[str, Any]:
    """List memories from Qdrant with in-memory pagination (fast for LAN scale)."""
    client, vs = _vector_store()
    if vs is None:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}

    page = max(1, page)
    size = max(1, min(size, 200))
    filters: dict[str, str] = {}
    if project:
        filters["project"] = project

    try:
        if search:
            from app.utils.partitioning import resolve_and_bind

            route = resolve_and_bind(client, project or "default")
            vectors = client.embedding_model.embed(search, "search")
            hits = client.vector_store.search(
                query=search,
                vectors=vectors,
                top_k=500,
                filters=filters or None,
                shard_key_selector=route.shard_key,
            )
            points = hits
        else:
            points = []
            offset = None
            scroll_filter = vs._create_filter(filters) if filters else None
            while True:
                records, offset = vs.client.scroll(
                    collection_name=vs.collection_name,
                    scroll_filter=scroll_filter,
                    limit=256,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points.extend(records or [])
                if offset is None:
                    break
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_shared_memories failed")
        raise RuntimeError(str(exc)) from exc

    items = []
    for p in points:
        payload = getattr(p, "payload", {}) or {}
        created = payload.get("created_at")
        items.append(
            {
                "id": str(getattr(p, "id", "")),
                "content": payload.get("data") or "",
                "created_at": created,
                "state": payload.get("state") or "active",
                "app_id": None,
                "app_name": payload.get("project") or project or "shared",
                "categories": [],
                "metadata_": payload,
            }
        )

    reverse = sort_direction.lower() != "asc"
    items.sort(key=lambda x: x.get("created_at") or "", reverse=reverse)

    total = len(items)
    pages = (total + size - 1) // size if total else 0
    start = (page - 1) * size
    page_items = items[start : start + size]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


def get_shared_memory_by_id(memory_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single memory point from Qdrant by ID (MCP write path)."""
    _, vs = _vector_store()
    if vs is None:
        return None
    try:
        records = vs.client.retrieve(
            collection_name=vs.collection_name,
            ids=[memory_id],
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            return None
        rec = records[0]
        payload = getattr(rec, "payload", {}) or {}
        created = payload.get("created_at")
        created_ts = 0
        if created:
            try:
                created_ts = int(
                    datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
                )
            except ValueError:
                created_ts = 0
        return {
            "id": str(getattr(rec, "id", memory_id)),
            "text": payload.get("data") or "",
            "created_at": created_ts,
            "state": payload.get("state") or "active",
            "app_id": None,
            "app_name": payload.get("project") or "shared",
            "categories": [],
            "metadata_": payload,
        }
    except Exception:  # noqa: BLE001
        logger.exception("failed to get shared memory %s", memory_id)
        return None
