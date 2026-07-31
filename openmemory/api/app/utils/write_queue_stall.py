"""Detect and materialize write-queue stalls for the admin UI.

When the write-worker process freezes or dies, jobs can sit forever in
``queued`` / ``processing`` with ``attempts=0`` — the UI never shows a failure
and ``retry-failed`` has nothing to reprocess.

This module runs inside the API process (always up). It watches the Redis
heartbeat from the write-worker; if the heartbeat is stale and there is backlog,
it marks stuck jobs as terminal ``failed`` with a clear error so operators can
reprocess from ``/admin/queues``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from app.utils.write_queue import write_queue as _default_write_queue
from app.utils.write_worker_heartbeat import (
    DEFAULT_STALE_SEC,
    worker_status,
)

logger = logging.getLogger(__name__)

DEFAULT_WATCHDOG_INTERVAL_SEC = 60.0
# Only fail queued jobs that have been waiting at least this long *and* the
# worker heartbeat is dead. Slow FIFO on limited HW must not look like a stall.
DEFAULT_QUEUED_FAIL_MINUTES = 10
# Processing jobs stuck longer than this (claim age) become failed when the
# worker is dead. Generous vs typical ~5–6 min/job on limited HW.
DEFAULT_PROCESSING_FAIL_MINUTES = 45

STALL_QUEUED_ERROR = (
    "Fila de escrita parada (worker sem heartbeat) — use Reprocessar Falhas"
)
STALL_PROCESSING_ERROR = (
    "Job travado em processing (worker sem heartbeat) — use Reprocessar Falhas"
)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def fail_stalled_jobs(
    *,
    queue=None,
    stale_sec: Optional[float] = None,
    queued_fail_minutes: Optional[int] = None,
    processing_fail_minutes: Optional[int] = None,
    force: bool = False,
) -> dict:
    """Fail stuck jobs when the write-worker heartbeat is stale.

    ``force=True`` skips the heartbeat check (manual admin action).
    Returns counts and worker status for the API response / logs.
    """
    q = queue if queue is not None else _default_write_queue
    stale = float(
        stale_sec
        if stale_sec is not None
        else _env_float("WRITE_WORKER_HEARTBEAT_STALE_SEC", DEFAULT_STALE_SEC)
    )
    queued_mins = int(
        queued_fail_minutes
        if queued_fail_minutes is not None
        else _env_int("WRITE_QUEUE_STALL_QUEUED_FAIL_MINUTES", DEFAULT_QUEUED_FAIL_MINUTES)
    )
    processing_mins = int(
        processing_fail_minutes
        if processing_fail_minutes is not None
        else _env_int(
            "WRITE_QUEUE_STALL_PROCESSING_FAIL_MINUTES",
            DEFAULT_PROCESSING_FAIL_MINUTES,
        )
    )

    status = worker_status(stale_sec=stale)
    if not force and not status["stalled"]:
        return {
            "stalled": False,
            "failed_queued": 0,
            "failed_processing": 0,
            "worker": status,
        }

    failed_processing = q.fail_stale_processing(
        processing_mins, STALL_PROCESSING_ERROR
    )
    failed_queued = q.fail_stalled_queued(queued_mins, STALL_QUEUED_ERROR)
    if failed_queued or failed_processing:
        logger.warning(
            "write-queue stall: marked failed queued=%s processing=%s "
            "heartbeat_age=%s force=%s",
            failed_queued,
            failed_processing,
            status.get("last_heartbeat_age_sec"),
            force,
        )
    return {
        "stalled": True if force else bool(status["stalled"]),
        "failed_queued": failed_queued,
        "failed_processing": failed_processing,
        "worker": status,
    }


class WriteQueueStallWatchdog:
    """Background loop in the API that materializes queue stalls as failures."""

    def __init__(
        self,
        interval_sec: float = DEFAULT_WATCHDOG_INTERVAL_SEC,
        queue=None,
    ):
        self._interval = max(5.0, float(interval_sec))
        self._queue = queue
        self._task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()

    def process_once(self) -> dict:
        return fail_stalled_jobs(queue=self._queue)

    async def run(self) -> None:
        logger.info(
            "write-queue stall watchdog started (interval=%ss)", self._interval
        )
        while not self._stopped.is_set():
            try:
                self.process_once()
            except Exception:  # noqa: BLE001
                logger.exception("write-queue stall watchdog pass failed")
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval
                )
            except asyncio.TimeoutError:
                pass
        logger.info("write-queue stall watchdog stopped")

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._stopped.clear()
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None


def watchdog_from_env() -> WriteQueueStallWatchdog:
    return WriteQueueStallWatchdog(
        interval_sec=_env_float(
            "WRITE_QUEUE_STALL_WATCHDOG_INTERVAL_SEC",
            DEFAULT_WATCHDOG_INTERVAL_SEC,
        )
    )


write_queue_stall_watchdog = watchdog_from_env()
