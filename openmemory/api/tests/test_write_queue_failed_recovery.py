"""Tests for failed-job cooldown recovery."""
import os
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import WriteQueueJob as WriteQueueModel
from app.models import WriteQueueStatus
from app.utils.write_queue import WriteJob, WriteQueue


def _make_queue(tmp_path, name="failed_recovery.db"):
    path = str(tmp_path / name)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    WriteQueueModel.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine)
    return WriteQueue(session_factory=factory), engine, factory, path


def _job():
    return WriteJob(
        id=str(uuid.uuid4()),
        project="p",
        hostname="h",
        client_name="c",
        text="t",
        created_at="",
    )


class TestRecoverFailedJobs:
    def test_failed_jobs_requeued_after_cooldown(self, tmp_path):
        q, engine, factory, path = _make_queue(tmp_path)
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)
        q.mark_failed(job_id, "llm down", attempts=3)

        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            row.updated_at = datetime.utcnow() - timedelta(minutes=20)
            db.commit()
        finally:
            db.close()

        assert q.recover_failed_jobs(15) == 1

        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            assert row.status == WriteQueueStatus.queued
            assert row.attempts == 0
            assert "auto-recovered" in (row.error or "")
        finally:
            db.close()
        engine.dispose()

    def test_recent_failed_jobs_not_recovered(self, tmp_path):
        q, engine, factory, path = _make_queue(tmp_path, "failed_recent.db")
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)
        q.mark_failed(job_id, "llm down", attempts=3)
        assert q.recover_failed_jobs(15) == 0
        engine.dispose()

    def test_disabled_when_minutes_zero(self, tmp_path):
        q, engine, _, _ = _make_queue(tmp_path, "failed_disabled.db")
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)
        q.mark_failed(job_id, "x", attempts=3)
        assert q.recover_failed_jobs(0) == 0
        engine.dispose()
