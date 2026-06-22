"""Manual requeue helpers for failed write-queue jobs."""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import WriteQueueJob, WriteQueueStatus


def requeue_failed_write_jobs(
    db: Session,
    *,
    project: Optional[str] = None,
) -> tuple[int, set[str]]:
    """Move all ``failed`` jobs back to ``queued`` and reset attempts.

    Returns ``(count, affected_project_names)``.
    """
    query = db.query(WriteQueueJob).filter(
        WriteQueueJob.status == WriteQueueStatus.failed
    )
    if project is not None:
        query = query.filter(WriteQueueJob.project == project)

    rows = query.all()
    if not rows:
        return 0, set()

    projects: set[str] = set()
    for row in rows:
        row.status = WriteQueueStatus.queued
        row.attempts = 0
        row.error = "reprocessamento manual (admin)"
        projects.add(row.project)

    db.commit()
    return len(rows), projects
