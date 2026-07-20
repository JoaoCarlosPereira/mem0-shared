"""Testes da task_05 (shared-specs): job de liberação de task por timeout.

Unitários cobrem a query de elegibilidade; o teste de integração roda
``process_once`` contra SQLite in-memory e confirma que a task travada volta
para ``tasks`` com ``changed_by="system:timeout"`` (ADR-007).
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Project,
    SpecWorkspace,
    TaskCard,
    TaskCardStatus,
    TaskStatusHistory,
    get_current_utc_time,
)
from app.workers.spec_task_timeout_worker import (
    TIMEOUT_ACTOR,
    SpecTaskTimeoutWorker,
)


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _mk_ws(db):
    db.add(Project(name="mem0-shared"))
    db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug="ws-1", name="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _mk_task(db, ws, *, status, activity_delta_hours, assignee="A", version=2):
    task = TaskCard(
        workspace_id=ws.id,
        title="Card",
        status=status,
        assignee=assignee,
        version=version,
        last_activity_at=get_current_utc_time() + timedelta(hours=activity_delta_hours),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


class TestEligibility:
    def test_em_andamento_alem_do_limite_e_elegivel(self, factory):
        worker = SpecTaskTimeoutWorker(timeout_hours=24, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db)
            _mk_task(db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-48)
            eligible = worker.eligible_tasks(db)
            assert len(eligible) == 1
        finally:
            db.close()

    def test_em_andamento_recente_nao_e_elegivel(self, factory):
        worker = SpecTaskTimeoutWorker(timeout_hours=24, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db)
            _mk_task(db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-1)
            assert worker.eligible_tasks(db) == []
        finally:
            db.close()

    def test_outro_status_nao_e_elegivel(self, factory):
        worker = SpecTaskTimeoutWorker(timeout_hours=24, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db)
            _mk_task(db, ws, status=TaskCardStatus.revisao_codigo, activity_delta_hours=-48)
            assert worker.eligible_tasks(db) == []
        finally:
            db.close()


class TestProcessOnce:
    def test_libera_task_travada_e_registra_system_timeout(self, factory):
        worker = SpecTaskTimeoutWorker(timeout_hours=24, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db)
            task = _mk_task(
                db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-48
            )
            task_id = task.id
        finally:
            db.close()

        released = worker.process_once()
        assert released == 1

        db = factory()
        try:
            fresh = db.query(TaskCard).filter_by(id=task_id).one()
            assert fresh.status == TaskCardStatus.tasks
            assert fresh.assignee is None
            hist = db.query(TaskStatusHistory).filter_by(task_id=task_id).one()
            assert hist.new_status == TaskCardStatus.tasks
            assert hist.changed_by == TIMEOUT_ACTOR
        finally:
            db.close()

    def test_nao_libera_task_dentro_do_limite(self, factory):
        worker = SpecTaskTimeoutWorker(timeout_hours=24, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db)
            _mk_task(db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-1)
        finally:
            db.close()

        assert worker.process_once() == 0

    def test_segunda_passada_nao_libera_de_novo(self, factory):
        """Idempotência: após liberar, a task não é mais elegível."""
        worker = SpecTaskTimeoutWorker(timeout_hours=24, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db)
            _mk_task(db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-48)
        finally:
            db.close()

        assert worker.process_once() == 1
        assert worker.process_once() == 0

    def test_process_once_engole_erros(self, factory):
        """Um erro na liberação não propaga (isolamento do worker)."""
        def boom(*args, **kwargs):
            raise RuntimeError("falha simulada")

        worker = SpecTaskTimeoutWorker(
            timeout_hours=24, session_factory=factory, release=boom
        )
        db = factory()
        try:
            ws = _mk_ws(db)
            _mk_task(db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-48)
        finally:
            db.close()

        assert worker.process_once() == 0


class TestGuardedReleaseIdempotency:
    def test_release_com_versao_desatualizada_e_noop(self, factory):
        """release_task com expected_version antigo não altera (outra réplica já liberou)."""
        from app.utils.task_lock import release_task

        db = factory()
        try:
            ws = _mk_ws(db)
            task = _mk_task(
                db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-48, version=5
            )
            # expected_version desatualizado -> no-op idempotente
            result = release_task(
                db, task.id, "system:timeout", expected_version=1
            )
            assert result.claimed is False
            db.refresh(task)
            assert task.status == TaskCardStatus.em_andamento  # inalterado
        finally:
            db.close()


class TestWorkerLifecycle:
    def test_start_processa_e_stop(self, factory):
        import asyncio

        worker = SpecTaskTimeoutWorker(
            timeout_hours=24, poll_seconds=0.05, session_factory=factory
        )
        db = factory()
        try:
            ws = _mk_ws(db)
            task = _mk_task(
                db, ws, status=TaskCardStatus.em_andamento, activity_delta_hours=-48
            )
            task_id = task.id
        finally:
            db.close()

        async def scenario():
            worker.start()
            await asyncio.sleep(0.15)  # deixa ao menos um process_once rodar
            await worker.stop()

        asyncio.run(scenario())

        db = factory()
        try:
            fresh = db.query(TaskCard).filter_by(id=task_id).one()
            assert fresh.status == TaskCardStatus.tasks
        finally:
            db.close()


def test_worker_from_env(monkeypatch):
    from app.workers.spec_task_timeout_worker import worker_from_env

    monkeypatch.setenv("SPEC_TASK_TIMEOUT_HOURS", "1")
    monkeypatch.setenv("SPEC_TASK_TIMEOUT_POLL_SECONDS", "5")
    w = worker_from_env()
    assert w._timeout.total_seconds() == 3600
    assert w._poll == 5
