"""Tests for stale processing recovery on write queue (task_03)."""

import os
import uuid

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import WriteQueueJob as WriteQueueModel
from app.models import WriteQueueStatus
from app.utils.write_queue import WriteJob, WriteQueue


def _make_queue(tmp_path, name="recovery.db"):
    path = str(tmp_path / name)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    WriteQueueModel.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine)
    return WriteQueue(session_factory=factory), engine, path


def _job():
    return WriteJob(
        id=str(uuid.uuid4()),
        project="p",
        hostname="h",
        client_name="c",
        text="t",
        created_at="",
    )


class TestRecoverStaleProcessing:
    def test_processing_jobs_return_to_queued(self, tmp_path):
        q, engine, path = _make_queue(tmp_path)
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)
        assert q.recover_stale_processing() == 1

        factory = sessionmaker(bind=create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False}))
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(WriteQueueModel.id == uuid.UUID(job_id)).first()
            assert row.status == WriteQueueStatus.queued
        finally:
            db.close()
        engine.dispose()

    def test_noop_when_no_processing_jobs(self, tmp_path):
        q, engine, _ = _make_queue(tmp_path, "recovery2.db")
        assert q.recover_stale_processing() == 0
        engine.dispose()

    def test_age_filter_skips_fresh_processing(self, tmp_path):
        from datetime import timedelta

        from app.utils.datetime_utc import utc_now_naive

        q, engine, path = _make_queue(tmp_path, "recovery3.db")
        job_id = q.enqueue(_job())
        q.dequeue(limit=1)

        factory = sessionmaker(
            bind=create_engine(
                f"sqlite:///{path}", connect_args={"check_same_thread": False}
            )
        )
        db = factory()
        try:
            row = db.query(WriteQueueModel).filter(
                WriteQueueModel.id == uuid.UUID(job_id)
            ).first()
            row.updated_at = utc_now_naive() - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        assert q.recover_stale_processing(older_than_minutes=15) == 0
        assert q.recover_stale_processing(older_than_minutes=1) == 1
        engine.dispose()
