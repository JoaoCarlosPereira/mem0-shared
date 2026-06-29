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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    GovernanceJob,
    GovernanceJobStatus,
    Project,
    WriteAuditLog,
    WriteQueueJob,
    WriteQueueStatus,
)
from app.schemas import (
    AdminOverviewResponse,
    BackupListResponse,
    BackupPolicySchema,
    BackupRestoreRequest,
    BackupStatusResponse,
    PaginatedWriteAuditResponse,
    PaginatedWriteQueueResponse,
    WriteAuditLogResponse,
    WriteQueueJobResponse,
)
from app.utils.backup import BackupService
from app.utils.backup_archive import BackupArchive
from app.utils.backup_policy import get_backup_policy, get_backup_policy_runtime, save_backup_policy
from app.utils.backup_paths import to_container_path
from app.utils.metrics import PROJECT_MEMORY_COUNT, PROJECT_SIZE_OVER_THRESHOLD
from app.utils.migration_control import MigrationControl, MigrationError, default_count_fn
from app.utils.promotion import PromotionService, default_promotion_service
from app.utils.vector_stats import (
    count_collection_memories,
    count_memories_last_24h,
    count_project_memories,
)

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
        count = count_project_memories(p.name)
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


@router.get("/projects/{project}/memories")
def project_memories(
    project: str,
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Lista as memórias de UM projeto lendo o store vetorial (Qdrant) — a MESMA
    fonte usada pelo MCP (list_memories/search_memory).

    O caminho de memória compartilhada grava via ``client.add(..., project=…)`` no
    Qdrant indexado por projeto; ele NÃO popula a tabela SQL ``memories`` (essa só
    recebe o que é criado pela UI/API por user_id). Por isso a leitura aqui é
    direta no vector store, por projeto, espelhando o ``list_memories`` do MCP.

    Imports do client de memória são lazy (puxam o mem0) para manter este módulo
    leve no import — os testes que path-load este arquivo não pagam esse custo.
    """
    from app.utils.memory import get_memory_client_safe
    from app.utils.partitioning import bind_active_collection, resolve_and_bind

    client = get_memory_client_safe()
    if client is None:
        raise HTTPException(status_code=503, detail="Memory system unavailable")

    filters = {"project": project}
    try:
        if search:
            route = resolve_and_bind(client, project)
            vectors = client.embedding_model.embed(search, "search")
            hits = client.vector_store.search(
                query=search, vectors=vectors, top_k=limit,
                filters=filters, shard_key_selector=route.shard_key,
            )
            items = [
                {
                    "id": str(getattr(h, "id", "")),
                    "memory": (getattr(h, "payload", {}) or {}).get("data"),
                    "created_at": (getattr(h, "payload", {}) or {}).get("created_at"),
                    "project": (getattr(h, "payload", {}) or {}).get("project"),
                    "score": getattr(h, "score", None),
                }
                for h in hits
            ]
        else:
            bind_active_collection(client)
            raw = client.vector_store.list(filters=filters, top_k=limit)
            # vector_store.list pode retornar (points, next_offset) ou lista flat.
            points = raw
            if isinstance(raw, (tuple, list)) and raw and isinstance(raw[0], (list, tuple)):
                points = raw[0]
            items = [
                {
                    "id": str(getattr(p, "id", "")),
                    "memory": (getattr(p, "payload", {}) or {}).get("data"),
                    "created_at": (getattr(p, "payload", {}) or {}).get("created_at"),
                    "project": (getattr(p, "payload", {}) or {}).get("project"),
                }
                for p in points
            ]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"erro lendo memórias do projeto: {exc}"
        ) from exc

    return {"project": project, "items": items, "total": len(items)}


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
# Backup / restore (task_04 / ADR-003, ADR-005)
#
# Os endpoints operam sobre BackupArchive (.zip unificado + rotação FIFO em
# diretório local, espelho S3 opcional). run/restore rodam em background (202).
# Restore exige confirmação forte (confirm == nome do arquivo) e dispara o
# snapshot de segurança automático (ver BackupArchive.restore / ADR-005).
# --------------------------------------------------------------------------- #
def _backup_archive(db: Session = Depends(get_db)) -> BackupArchive:
    """Build a BackupArchive wired to the live backends and persisted policy."""
    return BackupArchive(BackupService(), get_backup_policy_runtime(db))


def _ensure_writable(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
        if not os.access(path, os.W_OK):
            raise PermissionError(path)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"local_dir não gravável: {path}") from exc


@router.post("/backup/run", status_code=202)
def backup_run(
    background: BackgroundTasks,
    archive: BackupArchive = Depends(_backup_archive),
) -> dict:
    """Dispara um backup completo (Qdrant + PostgreSQL) em background."""
    background.add_task(archive.create)
    return {"status": "accepted"}


@router.get("/backup/status", response_model=BackupStatusResponse)
def backup_status(archive: BackupArchive = Depends(_backup_archive)) -> BackupStatusResponse:
    """Último backup, nº de cópias, idade (RPO) e último erro."""
    return BackupStatusResponse(**archive.status())


@router.get("/backup/list", response_model=BackupListResponse)
def backup_list(archive: BackupArchive = Depends(_backup_archive)) -> BackupListResponse:
    """Lista as cópias disponíveis (local + S3 quando espelhado)."""
    return BackupListResponse(archives=archive.list())


@router.get("/backup/policy", response_model=BackupPolicySchema)
def backup_policy_get(db: Session = Depends(get_db)) -> BackupPolicySchema:
    """Retorna a política de backup atual (defaults se ausente)."""
    return get_backup_policy(db)


@router.put("/backup/policy", response_model=BackupPolicySchema)
def backup_policy_put(payload: dict, db: Session = Depends(get_db)) -> BackupPolicySchema:
    """Valida (schema + local_dir gravável) e persiste a política de backup."""
    try:
        policy = BackupPolicySchema(**payload)
    except ValidationError as exc:
        detail = [{"campo": list(e.get("loc", [])), "erro": e.get("msg")} for e in exc.errors()]
        raise HTTPException(status_code=400, detail=detail) from exc
    _ensure_writable(to_container_path(policy.local_dir))
    return save_backup_policy(db, policy)


@router.post("/backup/restore", status_code=202)
def backup_restore(
    req: BackupRestoreRequest,
    background: BackgroundTasks,
    archive: BackupArchive = Depends(_backup_archive),
) -> dict:
    """Restore guiado: 404 se o arquivo não existe; 400 se a confirmação não bater."""
    if not archive.has(req.archive):
        raise HTTPException(status_code=404, detail=f"backup inexistente: {req.archive}")
    if req.confirm != req.archive:
        raise HTTPException(status_code=400, detail="confirmação não corresponde ao backup")
    background.add_task(archive.restore, archive.path_for(req.archive))
    return {"status": "accepted", "archive": req.archive}


# --------------------------------------------------------------------------- #
# Deletion guard (fail-closed — memórias críticas)
# --------------------------------------------------------------------------- #
@router.get("/deletion-guard")
def deletion_guard_admin() -> dict:
    """Expose current delete-protection flags for operators."""
    from app.utils.deletion_guard import deletion_guard_status

    status = deletion_guard_status()
    return {
        **status,
        "message": (
            "Deletes blocked (default). Set MEM0_ALLOW_MEMORY_DELETE=1 "
            "and optionally MEM0_ALLOW_BULK_DELETE=1 to enable."
            if not status["memory_delete_allowed"]
            else "Memory deletes are ENABLED — use with caution."
        ),
    }


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
    total_memories = count_collection_memories()
    memories_last_24h = count_memories_last_24h()

    return AdminOverviewResponse(
        total_projects=total_projects,
        total_memories=total_memories,
        memories_last_24h=memories_last_24h,
        write_queue_queued=_wq(WriteQueueStatus.queued),
        write_queue_processing=_wq(WriteQueueStatus.processing),
        write_queue_done=_wq(WriteQueueStatus.done),
        write_queue_skipped=_wq(WriteQueueStatus.skipped),
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
