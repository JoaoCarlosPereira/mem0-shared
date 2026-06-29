"""Delete a project and all associated memories (Qdrant + SQL catalog)."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    App,
    GovernanceJob,
    GovernancePolicy,
    GovernanceSchedule,
    Memory,
    MemoryAccessLog,
    MemoryState,
    Project,
    WriteAuditLog,
    WriteQueueJob,
)
from app.utils.deletion_guard import DeletionBlockedError, assert_bulk_delete_allowed
from app.utils.memory import get_memory_client_safe
from app.utils.partitioning import bind_active_collection
from app.utils.project_apps import resolve_project_name
from app.utils.read_cache import read_cache

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 128


def delete_qdrant_memories_for_project(project: str, *, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    """Remove all Qdrant points whose payload.project matches *project*."""
    memory_client = get_memory_client_safe()
    if memory_client is None:
        raise HTTPException(status_code=503, detail="Memory client is not available")

    bind_active_collection(memory_client)
    vs = memory_client.vector_store
    filt = vs._create_filter({"project": project})
    deleted = 0
    offset = None
    while True:
        records, offset = vs.client.scroll(
            collection_name=vs.collection_name,
            scroll_filter=filt,
            offset=offset,
            limit=batch_size,
            with_payload=False,
            with_vectors=False,
        )
        for rec in records or []:
            point_id = str(rec.id)
            try:
                memory_client.delete(point_id)
                deleted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to delete qdrant point %s for project %s: %s", point_id, project, exc)
        if offset is None:
            break
    return deleted


def cleanup_project_sql_references(db: Session, project: str) -> None:
    """Remove catalog rows and queue/audit references for a project name."""
    db.query(WriteQueueJob).filter(WriteQueueJob.project == project).delete(
        synchronize_session=False,
    )
    db.query(WriteAuditLog).filter(WriteAuditLog.project == project).delete(
        synchronize_session=False,
    )
    db.query(GovernanceJob).filter(GovernanceJob.project == project).delete(
        synchronize_session=False,
    )
    db.query(GovernanceSchedule).filter(GovernanceSchedule.scope == project).delete(
        synchronize_session=False,
    )
    policy = db.query(GovernancePolicy).filter(GovernancePolicy.project_name == project).first()
    if policy is not None:
        db.delete(policy)
    row = db.query(Project).filter(Project.name == project).first()
    if row is not None:
        db.delete(row)


def delete_project_by_name(
    db: Session,
    project: str,
    *,
    confirm_name: str,
) -> dict[str, int | str]:
    """Delete a MCP/Qdrant-backed project after name confirmation."""
    if confirm_name.strip() != project:
        raise HTTPException(
            status_code=400,
            detail="Confirmation name does not match the project name.",
        )

    try:
        assert_bulk_delete_allowed("project_delete")
    except DeletionBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    qdrant_deleted = delete_qdrant_memories_for_project(project)
    cleanup_project_sql_references(db, project)
    db.commit()
    read_cache.invalidate_search(project)

    return {
        "project": project,
        "deleted_memories": qdrant_deleted,
        "source": "project",
    }


def delete_legacy_sql_app(
    db: Session,
    app_id: UUID,
    *,
    confirm_name: str,
    user_id: str,
) -> dict[str, int | str]:
    """Delete a legacy SQL App row and its memories."""
    from app.routers.memories import get_or_create_user, update_memory_state

    app = db.query(App).filter(App.id == app_id).first()
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")

    if confirm_name.strip() != app.name:
        raise HTTPException(
            status_code=400,
            detail="Confirmation name does not match the project name.",
        )

    try:
        assert_bulk_delete_allowed("project_delete")
    except DeletionBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    user = get_or_create_user(db, user_id)
    memory_client = get_memory_client_safe()
    if memory_client is None:
        raise HTTPException(status_code=503, detail="Memory client is not available")

    memories = (
        db.query(Memory)
        .filter(
            Memory.app_id == app_id,
            Memory.state != MemoryState.deleted,
        )
        .all()
    )
    deleted = 0
    for memory in memories:
        try:
            memory_client.delete(str(memory.id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to delete memory %s from vector store: %s", memory.id, exc)
        update_memory_state(db, memory.id, MemoryState.deleted, user.id)
        deleted += 1

    db.query(MemoryAccessLog).filter(MemoryAccessLog.app_id == app_id).delete(
        synchronize_session=False,
    )
    db.delete(app)
    db.commit()

    return {
        "project": app.name,
        "deleted_memories": deleted,
        "source": "sql",
    }


def delete_app_or_project(
    db: Session,
    app_id: UUID,
    *,
    confirm_name: str,
    user_id: Optional[str] = None,
) -> dict[str, int | str]:
    """Entry point for DELETE project — resolves Qdrant project vs legacy SQL app."""
    project_name = resolve_project_name(db, app_id)
    if project_name:
        return delete_project_by_name(db, project_name, confirm_name=confirm_name)

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required for legacy app deletes")

    return delete_legacy_sql_app(
        db,
        app_id,
        confirm_name=confirm_name,
        user_id=user_id,
    )
