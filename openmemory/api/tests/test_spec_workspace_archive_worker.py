"""Testes do worker de auto-arquivamento (Tarefa kanban-archive-lifecycle).

Unitários cobrem a query de elegibilidade; o teste de integração roda
``process_once`` contra SQLite in-memory e confirma que o workspace concluído
há mais de N dias volta como ``arquivado``, com ``archived_by`` marcando a
transição como automática.
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Project, SpecWorkspace, SpecWorkspaceStatus, get_current_utc_time
from app.workers.spec_workspace_archive_worker import (
    AUTO_ARCHIVE_ACTOR,
    SpecWorkspaceArchiveWorker,
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


def _mk_ws(db, *, status, completed_delta_days=None):
    if not db.query(Project).filter(Project.name == "mem0-shared").first():
        db.add(Project(name="mem0-shared"))
        db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug="archive-ws", name="WS", status=status)
    if completed_delta_days is not None:
        ws.completed_at = get_current_utc_time() + timedelta(days=completed_delta_days)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


class TestEligibility:
    def test_concluido_alem_da_janela_e_elegivel(self, factory):
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-31)
            assert len(worker.eligible_workspaces(db)) == 1
        finally:
            db.close()

    def test_concluido_dentro_da_janela_nao_e_elegivel(self, factory):
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-1)
            assert worker.eligible_workspaces(db) == []
        finally:
            db.close()

    def test_concluido_sem_completed_at_nao_e_elegivel(self, factory):
        """Workspace legado (criado antes da feature) sem completed_at nunca dispara."""
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.concluido)
            assert worker.eligible_workspaces(db) == []
        finally:
            db.close()

    def test_outro_status_nao_e_elegivel(self, factory):
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.ativo, completed_delta_days=-31)
            assert worker.eligible_workspaces(db) == []
        finally:
            db.close()

    def test_ja_arquivado_nao_e_elegivel(self, factory):
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.arquivado, completed_delta_days=-31)
            assert worker.eligible_workspaces(db) == []
        finally:
            db.close()


class TestProcessOnce:
    def test_arquiva_workspace_vencido_e_registra_actor_automatico(self, factory):
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-31)
            ws_id = ws.id
        finally:
            db.close()

        assert worker.process_once() == 1

        db = factory()
        try:
            fresh = db.query(SpecWorkspace).filter_by(id=ws_id).one()
            assert fresh.status == SpecWorkspaceStatus.arquivado
            assert fresh.archived_by == AUTO_ARCHIVE_ACTOR
            assert fresh.archived_at is not None
        finally:
            db.close()

    def test_nao_arquiva_dentro_da_janela(self, factory):
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-1)
        finally:
            db.close()

        assert worker.process_once() == 0

    def test_segunda_passada_nao_arquiva_de_novo(self, factory):
        """Idempotência: após arquivar, o workspace não é mais elegível."""
        worker = SpecWorkspaceArchiveWorker(archive_after_days=30, session_factory=factory)
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-31)
        finally:
            db.close()

        assert worker.process_once() == 1
        assert worker.process_once() == 0

    def test_process_once_engole_erros(self, factory):
        """Um erro ao arquivar não propaga (isolamento do worker)."""

        def boom(*args, **kwargs):
            raise RuntimeError("falha simulada")

        worker = SpecWorkspaceArchiveWorker(
            archive_after_days=30, session_factory=factory, apply_change=boom
        )
        db = factory()
        try:
            _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-31)
        finally:
            db.close()

        assert worker.process_once() == 0


class TestWorkerLifecycle:
    def test_start_processa_e_stop(self, factory):
        import asyncio

        worker = SpecWorkspaceArchiveWorker(
            archive_after_days=30, poll_seconds=0.05, session_factory=factory
        )
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.concluido, completed_delta_days=-31)
            ws_id = ws.id
        finally:
            db.close()

        async def scenario():
            worker.start()
            await asyncio.sleep(0.15)  # deixa ao menos um process_once rodar
            await worker.stop()

        asyncio.run(scenario())

        db = factory()
        try:
            fresh = db.query(SpecWorkspace).filter_by(id=ws_id).one()
            assert fresh.status == SpecWorkspaceStatus.arquivado
        finally:
            db.close()


def test_worker_from_env(monkeypatch):
    from app.workers.spec_workspace_archive_worker import worker_from_env

    monkeypatch.setenv("SPEC_WORKSPACE_ARCHIVE_AFTER_DAYS", "45")
    monkeypatch.setenv("SPEC_WORKSPACE_ARCHIVE_POLL_SECONDS", "120")
    w = worker_from_env()
    assert w._window.total_seconds() == 45 * 86400
    assert w._poll == 120
