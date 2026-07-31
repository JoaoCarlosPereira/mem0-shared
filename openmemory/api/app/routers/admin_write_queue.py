"""Additional write-queue admin actions."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.admin_auth import require_admin
from app.utils.read_cache import read_cache
from app.utils.write_queue_requeue import requeue_done_write_jobs, requeue_failed_write_jobs
from app.utils.write_queue_stall import fail_stalled_jobs
from app.utils.write_worker_heartbeat import worker_status

router = APIRouter(prefix="/admin", tags=["admin"])


class RetryFailedWriteQueueResponse(BaseModel):
    requeued: int
    projects: list[str]


class WriteWorkerStatusResponse(BaseModel):
    alive: bool
    stalled: bool
    last_heartbeat_age_sec: Optional[float] = None
    stale_after_sec: float


class FailStalledWriteQueueResponse(BaseModel):
    stalled: bool
    failed_queued: int
    failed_processing: int
    worker: WriteWorkerStatusResponse


@router.get("/write-queue/worker-status", response_model=WriteWorkerStatusResponse)
def write_queue_worker_status(
    _: None = Depends(require_admin),
) -> WriteWorkerStatusResponse:
    """Heartbeat snapshot for the write-worker (stall detection)."""
    status = worker_status()
    return WriteWorkerStatusResponse(
        alive=bool(status.get("alive", True)),
        stalled=bool(status.get("stalled", False)),
        last_heartbeat_age_sec=status.get("last_heartbeat_age_sec"),
        stale_after_sec=float(status.get("stale_after_sec") or 90),
    )


@router.post("/write-queue/fail-stalled", response_model=FailStalledWriteQueueResponse)
def fail_stalled_write_queue_jobs(
    force: bool = Query(
        False,
        description="Fail stuck jobs even if heartbeat still looks alive",
    ),
    _: None = Depends(require_admin),
) -> FailStalledWriteQueueResponse:
    """Mark stuck queued/processing jobs as failed so the UI can reprocess them.

    Automatic watchdog already does this when the heartbeat is stale; this
    endpoint is the manual escape hatch.
    """
    result = fail_stalled_jobs(force=force)
    ww = result.get("worker") or {}
    return FailStalledWriteQueueResponse(
        stalled=bool(result.get("stalled")),
        failed_queued=int(result.get("failed_queued") or 0),
        failed_processing=int(result.get("failed_processing") or 0),
        worker=WriteWorkerStatusResponse(
            alive=bool(ww.get("alive", True)),
            stalled=bool(ww.get("stalled", False)),
            last_heartbeat_age_sec=ww.get("last_heartbeat_age_sec"),
            stale_after_sec=float(ww.get("stale_after_sec") or 90),
        ),
    )


@router.post("/write-queue/retry-failed", response_model=RetryFailedWriteQueueResponse)
def retry_failed_write_queue_jobs(
    db: Session = Depends(get_db),
    project: Optional[str] = Query(
        None, description="Requeue only failed jobs for this project"
    ),
    _: None = Depends(require_admin),
) -> RetryFailedWriteQueueResponse:
    """Re-queue all failed or skipped write jobs (optionally scoped to one project)."""
    count, projects = requeue_failed_write_jobs(db, project=project)
    for proj in projects:
        read_cache.invalidate_search(proj)
    return RetryFailedWriteQueueResponse(requeued=count, projects=sorted(projects))


@router.post("/write-queue/requeue-done", response_model=RetryFailedWriteQueueResponse)
def requeue_done_write_queue_jobs(
    db: Session = Depends(get_db),
    project: Optional[str] = Query(
        None, description="Requeue only done jobs for this project"
    ),
    _: None = Depends(require_admin),
) -> RetryFailedWriteQueueResponse:
    """Re-queue completed write jobs after vector-store data loss."""
    count, projects = requeue_done_write_jobs(db, project=project)
    for proj in projects:
        read_cache.invalidate_search(proj)
    return RetryFailedWriteQueueResponse(requeued=count, projects=sorted(projects))
