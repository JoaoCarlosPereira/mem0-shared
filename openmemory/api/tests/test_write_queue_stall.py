"""Tests for write-queue stall materialization (fail stuck jobs for UI retry)."""

import os
import uuid
from datetime import timedelta
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import WriteQueueJob as WriteQueueModel
from app.models import WriteQueueStatus
from app.utils.datetime_utc import utc_now_naive
from app.utils.write_queue import WriteJob, WriteQueue
from app.utils.write_queue_stall import fail_stalled_jobs


def _make_queue(tmp_path, name="stall.db"):
    path = str(tmp_path / name)
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    WriteQueueModel.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine)
    return WriteQueue(session_factory=factory), engine, path, factory


def _job(**kwargs):
    defaults = dict(
        id=str(uuid.uuid4()),
        project="p",
        hostname="h",
        client_name="c",
        text="t",
        created_at="",
    )
    defaults.update(kwargs)
    return WriteJob(**defaults)


class TestFailStaleHelpers:
    def test_fail_stale_processing(self, tmp_path):
        q, engine, path, factory = _make_queue(tmp_path)
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)

        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            row.updated_at = utc_now_naive() - timedelta(minutes=50)
            db.commit()
        finally:
            db.close()

        assert q.fail_stale_processing(40, "stuck") == 1
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row.status == WriteQueueStatus.failed
            assert row.error == "stuck"
        finally:
            db.close()
        engine.dispose()

    def test_fail_stalled_queued(self, tmp_path):
        q, engine, path, factory = _make_queue(tmp_path, "stall2.db")
        job_id = q.enqueue(_job())

        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            row.created_at = utc_now_naive() - timedelta(minutes=20)
            db.commit()
        finally:
            db.close()

        assert q.fail_stalled_queued(10, "worker dead") == 1
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row.status == WriteQueueStatus.failed
            assert "worker dead" in row.error
        finally:
            db.close()
        engine.dispose()

    def test_mark_done_if_processing_skips_failed(self, tmp_path):
        q, engine, _, _ = _make_queue(tmp_path, "stall3.db")
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)
        q.mark_failed(job_id, "timeout", attempts=1)
        assert q.mark_done_if_processing(job_id) is False
        info = q.get_job(job_id)
        assert info["status"] == "failed"
        engine.dispose()


class TestFailStalledJobs:
    def test_noop_when_worker_alive(self, tmp_path):
        q, engine, _, _ = _make_queue(tmp_path, "stall4.db")
        q.enqueue(_job())
        with patch(
            "app.utils.write_queue_stall.worker_status",
            return_value={
                "alive": True,
                "stalled": False,
                "last_heartbeat_age_sec": 5.0,
                "stale_after_sec": 90,
            },
        ):
            out = fail_stalled_jobs(queue=q)
        assert out["failed_queued"] == 0
        assert out["stalled"] is False
        engine.dispose()

    def test_fails_when_stalled(self, tmp_path):
        q, engine, path, factory = _make_queue(tmp_path, "stall5.db")
        job_id = q.enqueue(_job())
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            row.created_at = utc_now_naive() - timedelta(minutes=30)
            db.commit()
        finally:
            db.close()

        with patch(
            "app.utils.write_queue_stall.worker_status",
            return_value={
                "alive": False,
                "stalled": True,
                "last_heartbeat_age_sec": 200.0,
                "stale_after_sec": 90,
            },
        ):
            out = fail_stalled_jobs(
                queue=q, queued_fail_minutes=10, processing_fail_minutes=40
            )
        assert out["failed_queued"] == 1
        assert out["stalled"] is True
        engine.dispose()
