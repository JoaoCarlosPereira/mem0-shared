"""Administrative/operational endpoints for Fase 2 partitioning.

task_09: per-project size & health visibility so operators can promote a giant
project to a dedicated shard *before* it degrades search.

The promotion threshold is parameterizable via ``PROJECT_PROMOTION_THRESHOLD``
(number of memories); a project at/above it is flagged ``over_threshold`` and
counted in the ``project_size_over_threshold`` metric.

Migration control endpoints (start/flip/rollback, promote) are added to this same
router by task_07 / task_08.
"""

import csv
import io
import math
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    GovernanceJob,
    GovernanceJobStatus,
    Memory,
    MemoryState,
    Project,
    WriteAuditLog,
    WriteQueueJob,
    WriteQueueStatus,
)
from app.schemas import (
    AdminOverviewResponse,
    PaginatedWriteAuditResponse,
    PaginatedWriteQueueResponse,
    WriteAuditLogResponse,
    WriteQueueJobResponse,
)
from app.utils.backup import BackupService
from app.utils.metrics import PROJECT_MEMORY_COUNT, PROJECT_SIZE_OVER_THRESHOLD
from app.utils.migration_control import MigrationControl, MigrationError, default_count_fn
from app.utils.promotion import PromotionService, default_promotion_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _control() -> MigrationControl:
    """Build a MigrationControl wired to the live Qdrant count function."""
    return MigrationControl(count_fn=default_count_fn())


def _backup_service() -> BackupService:
    """Build a BackupService wired to the live S3/Qdrant/PostgreSQL backends."""
    return BackupService()


def _promotion() -> PromotionService:
    """Build a PromotionService wired to the live vector store."""
    return default_promotion_service()


def promotion_threshold() -> int:
    """Memory count at/above which a project should be promoted (parameterizable)."""
    try:
        return int(os.getenv("PROJECT_PROMOTION_THRESHOLD", "10000000"))
    except ValueError:
        return 10_000_000


@router.get("/projects/sizes")
def project_sizes(db: Session = Depends(get_db)) -> dict:
    """List projects with size, partition tier/shard and proximity to the threshold."""
    threshold = promotion_threshold()
    projects = db.query(Project).all()

    items = []
    over = 0
    for p in projects:
        count = p.memory_count or 0
        is_over = count >= threshold
        if is_over:
            over += 1
        tier = p.partition_tier.value if p.partition_tier is not None else "shared"
        # Refresh per-project gauge for Prometheus scraping.
        PROJECT_MEMORY_COUNT.labels(project=p.name).set(count)
        items.append(
            {
                "name": p.name,
                "memory_count": count,
                "partition_tier": tier,
                "shard_key": p.shard_key,
                "over_threshold": is_over,
            }
        )

    PROJECT_SIZE_OVER_THRESHOLD.set(over)
    return {"threshold": threshold, "over_threshold_count": over, "projects": items}


# --------------------------------------------------------------------------- #
# Migration control (task_07 / ADR-003)
# --------------------------------------------------------------------------- #
class StartMigrationRequest(BaseModel):
    source_collection: str
    target_collection: str


@router.post("/migration/start")
def migration_start(req: StartMigrationRequest, control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.start(req.source_collection, req.target_collection)
    except MigrationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/migration/validate")
def migration_validate(control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.validate()
    except MigrationError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/migration/flip")
def migration_flip(control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.flip()
    except MigrationError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/migration/rollback")
def migration_rollback(control: MigrationControl = Depends(_control)) -> dict:
    try:
        return control.rollback()
    except MigrationError as e:
        raise HTTPException(status_code=409, detail=str(e))


# --------------------------------------------------------------------------- #
# Tenant promotion (task_08 / ADR-002)
# --------------------------------------------------------------------------- #
@router.post("/projects/{name}/promote", status_code=202)
def promote_project(
    name: str,
    background: BackgroundTasks,
    service: PromotionService = Depends(_promotion),
) -> dict:
    """Enqueue promotion of a project to a dedicated shard key (non-blocking)."""
    background.add_task(service.promote, name)
    return {"status": "accepted", "project": name, "shard_key": name}


# --------------------------------------------------------------------------- #
# Backup / restore (task_03 / ADR-003)
# --------------------------------------------------------------------------- #
class RestoreRequest(BaseModel):
    key_prefix: str


@router.post("/backup/run", status_code=202)
def backup_run(
    background: BackgroundTasks,
    service: BackupService = Depends(_backup_service),
) -> dict:
    """Dispara um backup completo (Qdrant + PostgreSQL) em background."""
    background.add_task(service.run_backup)
    return {"status": "accepted"}


@router.get("/backup/status")
def backup_status(service: BackupService = Depends(_backup_service)) -> dict:
    """Último backup, total de objetos e idade (RPO corrente)."""
    return service.status()


@router.post("/backup/restore", status_code=202)
def backup_restore(
    req: RestoreRequest,
    background: BackgroundTasks,
    service: BackupService = Depends(_backup_service),
) -> dict:
    """Inicia restauração a partir de um prefixo de backup; 404 se inexistente."""
    if not service.exists(req.key_prefix):
        raise HTTPException(status_code=404, detail=f"no backup under {req.key_prefix}")
    background.add_task(service.restore, req.key_prefix)
    return {"status": "accepted", "key_prefix": req.key_prefix}


# --------------------------------------------------------------------------- #
# Admin dashboard: overview, write-queue & write-audit (Interface Admin)
# --------------------------------------------------------------------------- #
@router.get("/overview", response_model=AdminOverviewResponse)
def admin_overview(db: Session = Depends(get_db)) -> AdminOverviewResponse:
    """Aggregate real-time queue and system counts in a single response."""
    write_counts = dict(
        db.query(WriteQueueJob.status, func.count())
        .group_by(WriteQueueJob.status)
        .all()
    )
    gov_counts = dict(
        db.query(GovernanceJob.status, func.count())
        .group_by(GovernanceJob.status)
        .all()
    )

    def _wq(status: WriteQueueStatus) -> int:
        return write_counts.get(status, 0)

    def _gq(status: GovernanceJobStatus) -> int:
        return gov_counts.get(status, 0)

    total_projects = db.query(func.count(Project.name)).scalar() or 0
    total_memories = (
        db.query(func.count(Memory.id))
        .filter(Memory.state == MemoryState.active)
        .scalar()
        or 0
    )
    cutoff = datetime.utcnow() - timedelta(hours=24)
    memories_last_24h = (
        db.query(func.count(Memory.id)).filter(Memory.created_at >= cutoff).scalar() or 0
    )

    return AdminOverviewResponse(
        total_projects=total_projects,
        total_memories=total_memories,
        memories_last_24h=memories_last_24h,
        write_queue_queued=_wq(WriteQueueStatus.queued),
        write_queue_processing=_wq(WriteQueueStatus.processing),
        write_queue_failed=_wq(WriteQueueStatus.failed),
        governance_queue_queued=_gq(GovernanceJobStatus.queued),
        governance_queue_processing=_gq(GovernanceJobStatus.processing),
        governance_queue_failed=_gq(GovernanceJobStatus.failed),
    )


@router.get("/write-queue", response_model=PaginatedWriteQueueResponse)
def write_queue(
    db: Session = Depends(get_db),
    status: str | None = Query(None),
    project: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> PaginatedWriteQueueResponse:
    """List write-queue jobs with optional filters, paginated, newest first."""
    status_filter = None
    if status is not None:
        try:
            status_filter = WriteQueueStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status '{status}'") from exc

    query = db.query(WriteQueueJob)
    if project is not None:
        query = query.filter(WriteQueueJob.project == project)
    if status_filter is not None:
        query = query.filter(WriteQueueJob.status == status_filter)

    total = query.order_by(None).count()

    # failed_count ignores the status filter but honours the project scope.
    failed_query = db.query(func.count(WriteQueueJob.id)).filter(
        WriteQueueJob.status == WriteQueueStatus.failed
    )
    if project is not None:
        failed_query = failed_query.filter(WriteQueueJob.project == project)
    failed_count = failed_query.scalar() or 0

    rows = (
        query.order_by(WriteQueueJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        WriteQueueJobResponse(
            id=str(row.id),
            project=row.project,
            hostname=row.hostname,
            client_name=row.client_name,
            text_preview=(row.text or "")[:120],
            status=row.status.value,
            error=row.error,
            attempts=row.attempts,
            created_at=row.created_at,
        )
        for row in rows
    ]

    pages = math.ceil(total / page_size) if total else 0
    return PaginatedWriteQueueResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        failed_count=failed_count,
    )


@router.get("/write-audit", response_model=None)
def write_audit(
    request: Request,
    db: Session = Depends(get_db),
    project: str | None = Query(None),
    hostname: str | None = Query(None),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
):
    """List write-audit logs, paginated, newest first; CSV export via Accept header."""
    query = db.query(WriteAuditLog)
    if project is not None:
        query = query.filter(WriteAuditLog.project == project)
    if hostname is not None:
        query = query.filter(WriteAuditLog.hostname == hostname)
    if from_date is not None:
        query = query.filter(WriteAuditLog.created_at >= from_date)
    if to_date is not None:
        query = query.filter(WriteAuditLog.created_at <= to_date)

    accept = request.headers.get("accept", "")
    if "text/csv" in accept:
        total = query.order_by(None).count()
        if total > 10000:
            raise HTTPException(
                status_code=400, detail="more than 10000 records; refine filters"
            )
        rows = query.order_by(WriteAuditLog.created_at.desc()).limit(10000).all()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["id", "job_id", "project", "hostname", "client_name", "action", "created_at"]
        )
        for row in rows:
            writer.writerow(
                [
                    str(row.id),
                    str(row.job_id) if row.job_id else "",
                    row.project,
                    row.hostname,
                    row.client_name or "",
                    row.action,
                    row.created_at.isoformat() if row.created_at else "",
                ]
            )
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit.csv"},
        )

    total = query.order_by(None).count()
    rows = (
        query.order_by(WriteAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        WriteAuditLogResponse(
            id=str(row.id),
            job_id=str(row.job_id) if row.job_id else None,
            project=row.project,
            hostname=row.hostname,
            client_name=row.client_name,
            action=row.action,
            created_at=row.created_at,
        )
        for row in rows
    ]
    pages = math.ceil(total / page_size) if total else 0
    return PaginatedWriteAuditResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
    )
