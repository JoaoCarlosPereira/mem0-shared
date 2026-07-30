"""Mark memories obsolete (superseded) in the shared Qdrant store.

Used by the write worker after a successful ``add`` with ``supersedes``, and by
the MCP ``mark_obsolete`` tool. Points are never deleted — only payload
``state`` / linkage fields change so search can hide them by default.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


def mark_points_obsolete(
    memory_client,
    memory_ids: Iterable[str],
    *,
    superseded_by: Optional[str] = None,
) -> dict:
    """Set ``state=obsolete`` on each existing Qdrant point.

    Returns ``{"updated": [...], "missing": [...]}``.
    """
    from app.utils.partitioning import bind_active_collection

    bind_active_collection(memory_client)
    vs = memory_client.vector_store
    updated: list[str] = []
    missing: list[str] = []
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "state": "obsolete",
        "superseded_at": now,
    }
    if superseded_by:
        payload["superseded_by"] = str(superseded_by)

    for raw_id in memory_ids:
        mid = str(raw_id or "").strip()
        if not mid:
            continue
        try:
            found = vs.client.retrieve(
                collection_name=vs.collection_name,
                ids=[mid],
                with_payload=False,
                with_vectors=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("retrieve before obsolete failed id=%s: %s", mid, exc)
            missing.append(mid)
            continue
        if not found:
            missing.append(mid)
            continue
        try:
            vs.client.set_payload(
                collection_name=vs.collection_name,
                payload=payload,
                points=[mid],
            )
            updated.append(mid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("set_payload obsolete failed id=%s: %s", mid, exc)
            missing.append(mid)

    return {"updated": updated, "missing": missing}
