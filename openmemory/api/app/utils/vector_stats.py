"""Qdrant-backed memory counts and listing for the admin dashboard and shared UI.

MCP writes land in the vector store (indexed by ``project``), not in the SQL
``memories`` table. These helpers read the live collection so counts and lists
match what operators see via MCP.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
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
    """Count write enqueues in the last 24 hours via the SQL audit log.

    The overview dashboard only needs a fast approximate signal; scrolling the
    entire Qdrant collection is O(n) and blocked the admin UI on LAN scale.
    """
    from sqlalchemy import func

    from app.database import SessionLocal
    from app.models import WriteAuditLog

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    db = SessionLocal()
    try:
        return (
            db.query(func.count(WriteAuditLog.id))
            .filter(
                WriteAuditLog.created_at >= cutoff,
                WriteAuditLog.action == "enqueue",
            )
            .scalar()
            or 0
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to count recent memories from audit log")
        return 0
    finally:
        db.close()


def _scroll_points(vs, *, filters: dict[str, str], search: Optional[str] = None) -> list:
    """Scroll Qdrant points, optionally filtering payload text (case-insensitive)."""
    needle = search.strip().casefold() if search and search.strip() else None
    scroll_filter = vs._create_filter(filters) if filters else None
    points: list = []
    offset = None
    while True:
        records, offset = vs.client.scroll(
            collection_name=vs.collection_name,
            scroll_filter=scroll_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for rec in records or []:
            if needle is not None:
                payload = getattr(rec, "payload", {}) or {}
                data = (payload.get("data") or "").casefold()
                if needle not in data:
                    continue
            points.append(rec)
        if offset is None:
            break
    return points


def list_shared_memories(
    *,
    search: Optional[str] = None,
    project: Optional[str] = None,
    page: int = 1,
    size: int = 10,
    sort_direction: str = "desc",
) -> dict[str, Any]:
    """List memories from Qdrant with in-memory pagination (fast for LAN scale)."""
    _, vs = _vector_store()
    if vs is None:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}

    page = max(1, page)
    size = max(1, min(size, 200))
    filters: dict[str, str] = {}
    if project:
        filters["project"] = project

    try:
        points = _scroll_points(vs, filters=filters, search=search)
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
                **_attribution_from_payload(payload),
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


def _attribution_from_payload(payload: dict[str, Any]) -> dict[str, Optional[str]]:
    """Extract write-time attribution stored in Qdrant payload (ADR-003)."""
    from app.utils.attribution import attribution_from_payload

    return attribution_from_payload(payload)


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
            **_attribution_from_payload(payload),
        }
    except Exception:  # noqa: BLE001
        logger.exception("failed to get shared memory %s", memory_id)
        return None


def get_shared_memories_by_ids(memory_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch-fetch memory points from Qdrant by ID."""
    if not memory_ids:
        return {}
    _, vs = _vector_store()
    if vs is None:
        return {}
    try:
        records = vs.client.retrieve(
            collection_name=vs.collection_name,
            ids=memory_ids,
            with_payload=True,
            with_vectors=False,
        )
    except Exception:  # noqa: BLE001
        logger.exception("failed to batch-get shared memories")
        return {}

    out: dict[str, dict[str, Any]] = {}
    for rec in records or []:
        payload = getattr(rec, "payload", {}) or {}
        mid = str(getattr(rec, "id", ""))
        if not mid:
            continue
        created = payload.get("created_at")
        created_ts = 0
        if created:
            try:
                created_ts = int(
                    datetime.fromisoformat(str(created).replace("Z", "+00:00")).timestamp()
                )
            except ValueError:
                created_ts = 0
        out[mid] = {
            "id": mid,
            "text": payload.get("data") or "",
            "created_at": created_ts,
            "state": payload.get("state") or "active",
            "app_id": None,
            "app_name": payload.get("project") or "shared",
            "categories": [],
            "metadata_": payload,
            **_attribution_from_payload(payload),
        }
    return out
