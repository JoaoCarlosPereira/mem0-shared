"""Admin governance endpoints (task_11)."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from app.database import get_db
from app.governance.quality_eval import get_last_quality
from app.models import (
    GovernanceJob,
    GovernanceJobStatus,
    GovernanceJobType,
    MemoryState,
    MemoryStatusHistory,
    Project,
)
from app.schemas import GovernanceJobResponse, PaginatedGovernanceJobResponse
from app.utils.governance_policy import (
    get_global_policy,
    list_policies,
    save_global_policy,
    save_project_override,
    validate_policy_document,
)
from app.utils.governance_queue import governance_queue
from app.utils.quarantine import QuarantineEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/governance", tags=["governance"])


class PolicyUpdate(BaseModel):
    policy: Dict[str, Any]


class EnqueueJobRequest(BaseModel):
    project: Optional[str] = None
    limit: int = 500


def _engine() -> QuarantineEngine:
    return QuarantineEngine()


@router.get("/policies")
def get_policies(db: Session = Depends(get_db)) -> dict:
    return list_policies(session_factory=lambda: db)


@router.put("/policies")
def put_global_policy(body: PolicyUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        saved = save_global_policy(db, body.policy)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"global": saved}


@router.put("/policies/{project}")
def put_project_policy(project: str, body: PolicyUpdate, db: Session = Depends(get_db)) -> dict:
    if db.query(Project).filter(Project.name == project).first() is None:
        raise HTTPException(status_code=404, detail=f"project '{project}' not found")
    try:
        validate_policy_document({**get_global_policy(db), **body.policy})
        saved = save_project_override(db, project, body.policy)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": project, "overrides": saved}


@router.post("/jobs/{job_type}", status_code=202)
def enqueue_job(job_type: str, body: EnqueueJobRequest) -> dict:
    allowed = {"dedup", "ttl_prune", "consolidate", "purge"}
    if job_type not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported job_type '{job_type}'")
    job_id = governance_queue.enqueue(
        job_type,
        project=body.project,
        payload={"limit": body.limit, "manual": True},
    )
    return {"job_id": job_id, "job_type": job_type, "status": "queued"}


@router.get("/jobs", response_model=PaginatedGovernanceJobResponse)
def list_governance_jobs(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaginatedGovernanceJobResponse:
    """List governance jobs with optional filters, paginated, newest first."""
    status_filter = None
    if status is not None:
        try:
            status_filter = GovernanceJobStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status '{status}'") from exc

    type_filter = None
    if job_type is not None:
        try:
            type_filter = GovernanceJobType(job_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid job_type '{job_type}'") from exc

    query = db.query(GovernanceJob)
    if project is not None:
        query = query.filter(GovernanceJob.project == project)
    if type_filter is not None:
        query = query.filter(GovernanceJob.job_type == type_filter)
    if status_filter is not None:
        query = query.filter(GovernanceJob.status == status_filter)

    total = query.order_by(None).count()

    # failed_count ignores the status filter but honours the project/job_type scope.
    failed_query = db.query(func.count(GovernanceJob.id)).filter(
        GovernanceJob.status == GovernanceJobStatus.failed
    )
    if project is not None:
        failed_query = failed_query.filter(GovernanceJob.project == project)
    if type_filter is not None:
        failed_query = failed_query.filter(GovernanceJob.job_type == type_filter)
    failed_count = failed_query.scalar() or 0

    rows = (
        query.order_by(GovernanceJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        GovernanceJobResponse(
            id=str(row.id),
            job_type=row.job_type.value,
            project=row.project,
            status=row.status.value,
            attempts=row.attempts,
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
    pages = math.ceil(total / page_size) if total else 0
    return PaginatedGovernanceJobResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        failed_count=failed_count,
    )


@router.get("/audit")
def governance_audit(
    db: Session = Depends(get_db),
    project: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    query = db.query(MemoryStatusHistory).order_by(MemoryStatusHistory.changed_at.desc())
    if state:
        try:
            target = MemoryState(state)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid state '{state}'") from exc
        query = query.filter(MemoryStatusHistory.new_state == target)
    if since:
        query = query.filter(MemoryStatusHistory.changed_at >= since)
    if until:
        query = query.filter(MemoryStatusHistory.changed_at <= until)
    rows = query.limit(limit).all()
    items = []
    for row in rows:
        items.append(
            {
                "memory_id": str(row.memory_id),
                "old_state": row.old_state.value,
                "new_state": row.new_state.value,
                "changed_at": row.changed_at.isoformat() if row.changed_at else None,
                "changed_by": str(row.changed_by),
            }
        )
    if project:
        # Filter in Python — history table has no project column.
        from app.models import Memory

        mem_ids = {
            str(m.id)
            for m in db.query(Memory).all()
            if (m.metadata_ or {}).get("project") == project
        }
        items = [i for i in items if i["memory_id"] in mem_ids]
    return {"items": items}


@router.post("/revert/{memory_id}")
def revert_memory(memory_id: UUID, engine: QuarantineEngine = Depends(_engine)) -> dict:
    ok = engine.revert(memory_id)
    if not ok:
        raise HTTPException(status_code=409, detail="memory is not quarantined or not found")
    return {"memory_id": str(memory_id), "state": "active"}


@router.get("/quality")
def governance_quality() -> dict:
    return get_last_quality()
