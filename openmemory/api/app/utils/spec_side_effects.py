"""Post-write side effects for Spec documents (index + optional PLANKA mirror).

``write_spec_document`` (MCP) and the REST document PUT must return as soon as
Postgres commits. Embedding via Ollama regularly exceeds the MCP client timeout
(~30s); running index/mirror inline blocks the SSE event loop and surfaces as
``The operation timed out.`` even though the document was already saved.

Side effects are best-effort: failures are logged and never raised to the writer.
"""

from __future__ import annotations

import logging
import threading
from uuid import UUID

from app.database import SessionLocal

logger = logging.getLogger(__name__)


def schedule_document_post_write(
    workspace_id: UUID,
    document_type: str,
    *,
    mirror: bool = False,
) -> None:
    """Fire-and-forget index (+ optional PLANKA mirror) after a successful write.

    Opens a fresh DB session in a daemon thread so the caller can close its
    session and return immediately.
    """

    def _run() -> None:
        from app.models import SpecDocument, SpecWorkspace, parse_document_type
        from app.utils.spec_search import index_document_now

        db = SessionLocal()
        try:
            dtype = parse_document_type(document_type)
            ws = db.query(SpecWorkspace).filter(SpecWorkspace.id == workspace_id).first()
            if ws is None:
                logger.warning(
                    "spec-side-effects: workspace %s missing; skip index/mirror",
                    workspace_id,
                )
                return
            doc = (
                db.query(SpecDocument)
                .filter(
                    SpecDocument.workspace_id == workspace_id,
                    SpecDocument.document_type == dtype,
                )
                .first()
            )
            if doc is None:
                logger.warning(
                    "spec-side-effects: document %s/%s missing; skip",
                    workspace_id,
                    document_type,
                )
                return

            try:
                index_document_now(db, ws, doc)
            except Exception:  # noqa: BLE001 — never fail the writer
                logger.warning(
                    "spec-side-effects: index failed for %s/%s",
                    workspace_id,
                    document_type,
                    exc_info=True,
                )

            if mirror:
                from app.utils.planka_hooks import mirror_document_best_effort

                mirror_document_best_effort(db, workspace_id, dtype.value)
        finally:
            db.close()

    threading.Thread(
        target=_run,
        name=f"spec-post-write-{workspace_id}",
        daemon=True,
    ).start()
