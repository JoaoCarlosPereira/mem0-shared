"""Synchronous Spec → PLANKA mirror hooks (ADR-006).

Enabled when ``PLANKA_MIRROR_SYNC`` is truthy (compose sets ``1``). When disabled,
mutations succeed without calling PLANKA (tests / local without sidecar).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable, Optional, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.utils.planka import PlankaMirrorError, PlankaMirrorHttpClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


def mirror_sync_enabled() -> bool:
    raw = (os.getenv("PLANKA_MIRROR_SYNC") or "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _run_async(coro: Awaitable[T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already inside an event loop (e.g. MCP async tool): run in a fresh loop thread.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


async def _call(
    db: Session,
    op: Callable[[PlankaMirrorHttpClient], Awaitable[T]],
) -> T:
    client = PlankaMirrorHttpClient(db)
    return await op(client)


def run_mirror(
    db: Session,
    op: Callable[[PlankaMirrorHttpClient], Awaitable[T]],
    *,
    action: str,
) -> Optional[T]:
    """Run a mirror op or no-op when disabled. Raises HTTPException 502 on failure."""
    if not mirror_sync_enabled():
        return None
    try:
        return _run_async(_call(db, op))
    except PlankaMirrorError as exc:
        logger.error("planka_mirror_failed action=%s status=%s detail=%s", action, exc.status_code, exc.detail)
        raise HTTPException(
            status_code=502,
            detail={
                "mirror_failed": True,
                "action": action,
                "planka_status": exc.status_code,
                "detail": exc.detail,
            },
        ) from exc


def mirror_task(db: Session, task_id: UUID) -> None:
    run_mirror(db, lambda c: c.mirror_task(task_id), action="mirror_task")


def mirror_task_status(db: Session, task_id: UUID) -> None:
    run_mirror(db, lambda c: c.mirror_task_status(task_id), action="mirror_task_status")


def mirror_document(db: Session, workspace_id: UUID, doc_type: str) -> None:
    run_mirror(
        db,
        lambda c: c.mirror_document(workspace_id, doc_type),
        action="mirror_document",
    )


def mirror_ensure_workspace(db: Session, workspace_id: UUID) -> None:
    run_mirror(
        db,
        lambda c: c.ensure_workspace_board(workspace_id),
        action="ensure_workspace_board",
    )


def mirror_delete_task(db: Session, task_id: UUID) -> None:
    run_mirror(db, lambda c: c.delete_task(task_id), action="delete_task")
