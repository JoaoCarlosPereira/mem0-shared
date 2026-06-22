"""Additional write-queue admin actions."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.read_cache import read_cache
from app.utils.write_queue_requeue import requeue_failed_write_jobs

router = APIRouter(prefix="/admin", tags=["admin"])


class RetryFailedWriteQueueResponse(BaseModel):
    requeued: int
    projects: list[str]


@router.post("/write-queue/retry-failed", response_model=RetryFailedWriteQueueResponse)
def retry_failed_write_queue_jobs(
    db: Session = Depends(get_db),
    project: Optional[str] = Query(
        None, description="Requeue only failed jobs for this project"
    ),
) -> RetryFailedWriteQueueResponse:
    """Re-queue all failed write jobs (optionally scoped to one project)."""
    count, projects = requeue_failed_write_jobs(db, project=project)
    for proj in projects:
        read_cache.invalidate_search(proj)
    return RetryFailedWriteQueueResponse(requeued=count, projects=sorted(projects))
