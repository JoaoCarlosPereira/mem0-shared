"""Manual requeue helpers for failed write-queue jobs."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import WriteQueueJob, WriteQueueStatus


def requeue_failed_write_jobs(
    db: Session,
    *,
    project: Optional[str] = None,
) -> tuple[int, set[str]]:
    """Move all ``failed`` or ``skipped`` jobs back to ``queued`` and reset attempts.

    Returns ``(count, affected_project_names)``.
    """
    return _requeue_jobs(
        db,
        statuses=[WriteQueueStatus.failed, WriteQueueStatus.skipped],
        project=project,
        error_note="reprocessamento manual (admin)",
    )


def requeue_done_write_jobs(
    db: Session,
    *,
    project: Optional[str] = None,
) -> tuple[int, set[str]]:
    """Move all ``done`` jobs back to ``queued`` for disaster recovery.

    Used when the vector store was wiped but the durable write queue still
    holds the original texts. Returns ``(count, affected_project_names)``.
    """
    return _requeue_jobs(
        db,
        statuses=[WriteQueueStatus.done],
        project=project,
        error_note="reprocessamento recuperacao qdrant",
    )


def _requeue_jobs(
    db: Session,
    *,
    statuses: list[WriteQueueStatus],
    project: Optional[str],
    error_note: str,
) -> tuple[int, set[str]]:
    query = db.query(WriteQueueJob).filter(WriteQueueJob.status.in_(statuses))
    if project is not None:
        query = query.filter(WriteQueueJob.project == project)

    rows = query.all()
    if not rows:
        return 0, set()

    projects: set[str] = set()
    for row in rows:
        row.status = WriteQueueStatus.queued
        row.attempts = 0
        row.error = error_note
        projects.add(row.project)

    db.commit()
    return len(rows), projects
