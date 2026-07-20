"""Testes da task_01 (shared-specs): modelos e migração das tabelas de specs.

Unitários rodam em SQLite em memória (padrão do repo). A migração Alembic é
exercitada de verdade em um SQLite de arquivo temporário (a cadeia inteira é
dialect-aware), cobrindo criação e remoção das 7 tabelas sem depender de
PostgreSQL — os asserts específicos de PG vivem em ``test_postgres_migrations.py``.
"""

from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    CommentTargetType,
    DocumentOrigin,
    DocumentType,
    Project,
    SpecAuditLog,
    SpecComment,
    SpecDocument,
    SpecDocumentVersion,
    SpecWorkspace,
    SpecWorkspaceStatus,
    TaskCard,
    TaskCardStatus,
    TaskStatusHistory,
)

_SPEC_TABLES = {
    "spec_workspaces",
    "spec_documents",
    "spec_document_versions",
    "task_cards",
    "task_status_history",
    "spec_audit_logs",
    "spec_comments",
}


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


def _mk_workspace(db, project_name="mem0-shared", slug="ws-1") -> SpecWorkspace:
    db.add(Project(name=project_name))
    db.commit()
    ws = SpecWorkspace(project_id=project_name, slug=slug, name="Workspace 1")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


class TestSpecModelsPersistence:
    """1.5 / Testes: criar uma instância de cada model e persistir com sucesso."""

    def test_workspace_persiste_com_status_default(self, db_session):
        ws = _mk_workspace(db_session)
        found = db_session.query(SpecWorkspace).one()
        assert found.id == ws.id
        assert found.status == SpecWorkspaceStatus.planejamento
        assert found.project.name == "mem0-shared"

    def test_document_e_versao_persistem(self, db_session):
        ws = _mk_workspace(db_session)
        doc = SpecDocument(
            workspace_id=ws.id,
            document_type=DocumentType.prd,
            current_version=1,
            current_content="# PRD v1",
        )
        db_session.add(doc)
        db_session.commit()
        version = SpecDocumentVersion(
            document_id=doc.id,
            version=1,
            content="# PRD v1",
            author="joao@sysmo.com.br",
            origin=DocumentOrigin.mcp,
        )
        db_session.add(version)
        db_session.commit()

        db_session.refresh(doc)
        assert doc.current_version == 1
        assert doc.versions[0].origin == DocumentOrigin.mcp
        assert version.document.document_type == DocumentType.prd

    def test_taskcard_persiste_com_defaults(self, db_session):
        ws = _mk_workspace(db_session)
        card = TaskCard(workspace_id=ws.id, title="Implementar login")
        db_session.add(card)
        db_session.commit()

        db_session.refresh(card)
        assert card.status == TaskCardStatus.tasks
        assert card.is_blocked is False
        assert card.version == 1
        assert card.block_reason is None

    def test_taskcard_bloqueado_e_ortogonal_ao_status(self, db_session):
        ws = _mk_workspace(db_session)
        card = TaskCard(
            workspace_id=ws.id,
            title="Card bloqueado",
            status=TaskCardStatus.em_andamento,
            is_blocked=True,
            block_reason="Aguardando dependência externa",
        )
        db_session.add(card)
        db_session.commit()

        db_session.refresh(card)
        # bloqueio não muda a coluna atual
        assert card.status == TaskCardStatus.em_andamento
        assert card.is_blocked is True
        assert card.block_reason == "Aguardando dependência externa"

    def test_status_history_espelha_memory_history(self, db_session):
        ws = _mk_workspace(db_session)
        card = TaskCard(workspace_id=ws.id, title="Card")
        db_session.add(card)
        db_session.commit()
        hist = TaskStatusHistory(
            task_id=card.id,
            old_status=TaskCardStatus.tasks,
            new_status=TaskCardStatus.em_andamento,
            changed_by="DESKTOP-01",
        )
        db_session.add(hist)
        db_session.commit()

        found = db_session.query(TaskStatusHistory).one()
        assert found.old_status == TaskCardStatus.tasks
        assert found.new_status == TaskCardStatus.em_andamento
        assert found.task.id == card.id

    def test_audit_log_grava_json_e_origin(self, db_session):
        ws = _mk_workspace(db_session)
        log = SpecAuditLog(
            workspace_id=ws.id,
            actor="joao@sysmo.com.br",
            action="write_spec_document",
            detail={"document_type": "prd", "version": 2},
            origin=DocumentOrigin.api,
        )
        db_session.add(log)
        db_session.commit()

        found = db_session.query(SpecAuditLog).one()
        assert found.detail == {"document_type": "prd", "version": 2}
        assert found.origin == DocumentOrigin.api
        assert found.workspace.id == ws.id

    def test_comment_polimorfico_persiste(self, db_session):
        ws = _mk_workspace(db_session)
        comment = SpecComment(
            target_type=CommentTargetType.workspace,
            target_id=ws.id,
            author="joao@sysmo.com.br",
            body="Comentário de teste",
        )
        db_session.add(comment)
        db_session.commit()

        found = db_session.query(SpecComment).one()
        assert found.target_type == CommentTargetType.workspace
        assert found.target_id == ws.id


class TestSpecModelsConstraints:
    def test_versao_duplicada_viola_unicidade(self, db_session):
        ws = _mk_workspace(db_session)
        doc = SpecDocument(
            workspace_id=ws.id, document_type=DocumentType.prd, current_content="x"
        )
        db_session.add(doc)
        db_session.commit()
        db_session.add(
            SpecDocumentVersion(
                document_id=doc.id, version=1, content="a", origin=DocumentOrigin.mcp
            )
        )
        db_session.commit()
        db_session.add(
            SpecDocumentVersion(
                document_id=doc.id, version=1, content="b", origin=DocumentOrigin.mcp
            )
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_documento_duplicado_por_tipo_viola_unicidade(self, db_session):
        ws = _mk_workspace(db_session)
        db_session.add(
            SpecDocument(workspace_id=ws.id, document_type=DocumentType.prd, current_content="a")
        )
        db_session.commit()
        db_session.add(
            SpecDocument(workspace_id=ws.id, document_type=DocumentType.prd, current_content="b")
        )
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_workspace_sem_project_id_falha(self, db_session):
        # project_id é obrigatório (NOT NULL) — SpecWorkspace sempre é filho de Project.
        db_session.add(SpecWorkspace(slug="órfã", name="Sem projeto"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_workspace_slug_unico_por_projeto(self, db_session):
        _mk_workspace(db_session, project_name="p1", slug="dup")
        db_session.add(SpecWorkspace(project_id="p1", slug="dup", name="Duplicada"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestSpecMigrationSqlite:
    """Exercita a migração real (upgrade/downgrade) das 7 tabelas em SQLite."""

    @pytest.fixture
    def alembic_cfg(self, tmp_path, monkeypatch):
        from alembic.config import Config

        db_path = tmp_path / "specs.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        ini = tmp_path / "alembic.ini"
        ini.write_text(
            "[alembic]\n"
            "script_location = alembic\n"
            "sqlalchemy.url = driver://user:pass@localhost/dbname\n"
            "\n"
            "[loggers]\nkeys = root\n\n"
            "[handlers]\nkeys = console\n\n"
            "[formatters]\nkeys = generic\n\n"
            "[logger_root]\nlevel = WARN\nhandlers = console\n\n"
            "[handler_console]\nclass = StreamHandler\n"
            "args = (sys.stderr,)\nlevel = NOTSET\nformatter = generic\n\n"
            "[formatter_generic]\nformat = %(levelname)s %(message)s\n"
        )
        cfg = Config(str(ini))
        cfg.set_main_option(
            "script_location",
            str(Path(__file__).resolve().parents[1] / "alembic"),
        )
        return cfg, f"sqlite:///{db_path}"

    def test_upgrade_cria_tabelas_e_downgrade_remove(self, alembic_cfg):
        from alembic import command

        cfg, url = alembic_cfg

        # Sobe até a revisão anterior às specs: nenhuma tabela de specs existe.
        command.upgrade(cfg, "h3c4d5e6f7a8")
        eng = create_engine(url)
        tables = set(sa.inspect(eng).get_table_names())
        assert not (_SPEC_TABLES & tables)

        # upgrade head cria as 7 tabelas.
        command.upgrade(cfg, "head")
        tables = set(sa.inspect(eng).get_table_names())
        assert _SPEC_TABLES <= tables

        # Índices/constraints-chave materializados.
        version_uniques = {
            uc["name"]
            for uc in sa.inspect(eng).get_unique_constraints("spec_document_versions")
        }
        assert "uq_spec_version_document_version" in version_uniques
        task_indexes = {idx["name"] for idx in sa.inspect(eng).get_indexes("task_cards")}
        assert "idx_task_card_workspace_status" in task_indexes

        # Idempotência: downgrade + upgrade novamente não quebra.
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")
        tables = set(sa.inspect(eng).get_table_names())
        assert _SPEC_TABLES <= tables

        # downgrade -1 remove exatamente as 7 tabelas de specs.
        command.downgrade(cfg, "-1")
        tables = set(sa.inspect(eng).get_table_names())
        assert not (_SPEC_TABLES & tables)
        # Tabelas pré-existentes permanecem (mudança aditiva).
        assert "projects" in tables and "users" in tables
        eng.dispose()
