"""Testes da task_02 (shared-specs): versionamento e lock de concorrência.

Cobrem detecção de conflito por ``expected_version`` (ADR-005) e a
exclusividade de claim de task (ADR-003/ADR-007) nos utilitários de domínio
``app.utils.spec_versioning`` e ``app.utils.task_lock``.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    DocumentOrigin,
    DocumentType,
    Project,
    SpecAuditLog,
    SpecDocument,
    SpecDocumentVersion,
    TaskCard,
    TaskCardStatus,
    TaskStatusHistory,
)
from app.utils.spec_versioning import write_document_version
from app.utils.task_lock import claim_task, release_task, update_task_status


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _mk_workspace(db):
    from app.models import SpecWorkspace

    db.add(Project(name="mem0-shared"))
    db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug="ws-1", name="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _mk_document(db, ws):
    """SpecDocument recém-criado, sem versão (current_version=0)."""
    doc = SpecDocument(workspace_id=ws.id, document_type=DocumentType.prd)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _mk_task(db, ws, **kwargs):
    task = TaskCard(workspace_id=ws.id, title="Card", **kwargs)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


class TestWriteDocumentVersion:
    def test_criacao_inicial_com_expected_none(self, db_session):
        ws = _mk_workspace(db_session)
        doc = _mk_document(db_session, ws)
        assert doc.current_version == 0

        res = write_document_version(
            db_session, doc.id, "# PRD v1", None, "joao@sysmo.com.br", DocumentOrigin.mcp
        )
        assert res.conflict is False
        assert res.version == 1

        db_session.refresh(doc)
        assert doc.current_version == 1
        assert doc.current_content == "# PRD v1"
        versions = db_session.query(SpecDocumentVersion).filter_by(document_id=doc.id).all()
        assert len(versions) == 1 and versions[0].version == 1
        # auditoria registrada
        assert db_session.query(SpecAuditLog).filter_by(action="write_spec_document").count() == 1

    def test_caminho_feliz_incrementa_versao(self, db_session):
        ws = _mk_workspace(db_session)
        doc = _mk_document(db_session, ws)
        write_document_version(db_session, doc.id, "v1", None, "a", DocumentOrigin.api)

        res = write_document_version(db_session, doc.id, "v2", 1, "b", DocumentOrigin.api)
        assert res.conflict is False
        assert res.version == 2
        db_session.refresh(doc)
        assert doc.current_version == 2
        assert doc.current_content == "v2"
        assert db_session.query(SpecDocumentVersion).filter_by(document_id=doc.id).count() == 2

    def test_conflito_nao_altera_nem_cria_versao(self, db_session):
        ws = _mk_workspace(db_session)
        doc = _mk_document(db_session, ws)
        write_document_version(db_session, doc.id, "v1", None, "a", DocumentOrigin.api)
        write_document_version(db_session, doc.id, "v2", 1, "a", DocumentOrigin.api)
        # current_version agora é 2; gravar com expected_version=1 (desatualizado)
        res = write_document_version(db_session, doc.id, "v-conflito", 1, "c", DocumentOrigin.api)

        assert res.conflict is True
        assert res.version == 2
        assert res.current_content == "v2"
        db_session.refresh(doc)
        assert doc.current_version == 2
        assert doc.current_content == "v2"
        # nenhuma versão v3 criada
        assert db_session.query(SpecDocumentVersion).filter_by(document_id=doc.id).count() == 2

    def test_string_origin_e_coagida(self, db_session):
        ws = _mk_workspace(db_session)
        doc = _mk_document(db_session, ws)
        write_document_version(db_session, doc.id, "v1", None, "a", "ui")
        v = db_session.query(SpecDocumentVersion).filter_by(document_id=doc.id).one()
        assert v.origin == DocumentOrigin.ui


class TestConcurrentWrites:
    def test_duas_gravacoes_mesma_origem_segunda_conflita(self, db_session):
        """Duas gravações partindo da mesma versão de origem: a 2ª conflita."""
        ws = _mk_workspace(db_session)
        doc = _mk_document(db_session, ws)
        write_document_version(db_session, doc.id, "base", None, "a", DocumentOrigin.api)
        # Ambos os clientes leram version=1.
        first = write_document_version(db_session, doc.id, "cliente-A", 1, "A", DocumentOrigin.api)
        second = write_document_version(db_session, doc.id, "cliente-B", 1, "B", DocumentOrigin.api)

        assert first.conflict is False and first.version == 2
        assert second.conflict is True and second.version == 2
        db_session.refresh(doc)
        assert doc.current_content == "cliente-A"  # sem perda silenciosa


class TestClaimTask:
    def test_claim_em_task_disponivel_atribui_e_move_status(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(db_session, ws)
        assert task.status == TaskCardStatus.tasks

        res = claim_task(db_session, task.id, "DESKTOP-01")
        assert res.claimed is True
        assert res.current_assignee == "DESKTOP-01"
        db_session.refresh(task)
        assert task.status == TaskCardStatus.em_andamento
        assert task.assignee == "DESKTOP-01"
        # histórico registrado
        assert db_session.query(TaskStatusHistory).filter_by(task_id=task.id).count() == 1

    def test_claim_em_task_ja_ativa_falha_e_preserva_assignee(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(db_session, ws)
        claim_task(db_session, task.id, "DESKTOP-01")

        res = claim_task(db_session, task.id, "DESKTOP-02")
        assert res.claimed is False
        assert res.current_assignee == "DESKTOP-01"
        db_session.refresh(task)
        assert task.assignee == "DESKTOP-01"  # inalterado
        assert task.status == TaskCardStatus.em_andamento


class TestReleaseTask:
    def test_release_limpa_assignee_bloqueio_e_volta_para_tasks(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(
            db_session,
            ws,
            status=TaskCardStatus.em_andamento,
            assignee="DESKTOP-01",
            is_blocked=True,
            block_reason="travado",
        )

        res = release_task(db_session, task.id, "admin", reason="timeout")
        assert res.claimed is False
        db_session.refresh(task)
        assert task.status == TaskCardStatus.tasks
        assert task.assignee is None
        assert task.is_blocked is False
        assert task.block_reason is None
        hist = db_session.query(TaskStatusHistory).filter_by(task_id=task.id).one()
        assert hist.old_status == TaskCardStatus.em_andamento
        assert hist.new_status == TaskCardStatus.tasks

    def test_apos_release_task_pode_ser_reivindicada(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(db_session, ws)
        claim_task(db_session, task.id, "DESKTOP-01")
        release_task(db_session, task.id, "admin")

        res = claim_task(db_session, task.id, "DESKTOP-02")
        assert res.claimed is True
        assert res.current_assignee == "DESKTOP-02"


class TestUpdateTaskStatus:
    def test_muda_status_com_versao_correta(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(db_session, ws, status=TaskCardStatus.em_andamento, version=1)

        res = update_task_status(
            db_session, task.id, TaskCardStatus.revisao_codigo, 1, "DESKTOP-01"
        )
        assert res.updated is True and res.conflict is False
        assert res.status == "revisao_codigo"
        db_session.refresh(task)
        assert task.status == TaskCardStatus.revisao_codigo
        assert task.version == 2

    def test_conflito_de_versao_nao_altera(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(db_session, ws, status=TaskCardStatus.em_andamento, version=3)

        res = update_task_status(
            db_session, task.id, TaskCardStatus.concluido, 1, "DESKTOP-01"
        )
        assert res.updated is False and res.conflict is True
        assert res.version == 3
        db_session.refresh(task)
        assert task.status == TaskCardStatus.em_andamento
        assert task.version == 3

    def test_reportar_bloqueio_mantem_status(self, db_session):
        ws = _mk_workspace(db_session)
        task = _mk_task(db_session, ws, status=TaskCardStatus.em_andamento, version=1)

        res = update_task_status(
            db_session,
            task.id,
            TaskCardStatus.em_andamento,
            1,
            "DESKTOP-01",
            is_blocked=True,
            block_reason="dependência externa",
        )
        assert res.updated is True
        db_session.refresh(task)
        assert task.status == TaskCardStatus.em_andamento
        assert task.is_blocked is True
        assert task.block_reason == "dependência externa"
