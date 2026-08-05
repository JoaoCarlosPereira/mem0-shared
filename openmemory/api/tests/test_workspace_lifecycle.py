"""Testes de ``apply_status_change`` (Tarefa kanban-archive-lifecycle).

Cobre os timestamps de conclusão/arquivamento no ``SpecWorkspace`` e o
espelho best-effort para o PLANKA — sem sidecar real (``PLANKA_MIRROR_SYNC``
desligado por padrão nos testes, então o hook é no-op).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Project, SpecWorkspace, SpecWorkspaceStatus
from app.utils.workspace_lifecycle import apply_status_change


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


def _mk_ws(db, *, status=SpecWorkspaceStatus.ativo) -> SpecWorkspace:
    if not db.query(Project).filter(Project.name == "mem0-shared").first():
        db.add(Project(name="mem0-shared"))
        db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug="lifecycle-ws", name="Lifecycle", status=status)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


class TestConcluido:
    def test_marca_completed_at_na_primeira_conclusao(self, db_session):
        ws = _mk_ws(db_session)
        apply_status_change(db_session, ws, SpecWorkspaceStatus.concluido)
        assert ws.status == SpecWorkspaceStatus.concluido
        assert ws.completed_at is not None
        assert ws.archived_at is None

    def test_segunda_conclusao_nao_sobrescreve_completed_at(self, db_session):
        ws = _mk_ws(db_session)
        apply_status_change(db_session, ws, SpecWorkspaceStatus.concluido)
        first = ws.completed_at
        apply_status_change(db_session, ws, SpecWorkspaceStatus.concluido)
        assert ws.completed_at == first


class TestArquivado:
    def test_marca_archived_at_e_archived_by(self, db_session):
        ws = _mk_ws(db_session, status=SpecWorkspaceStatus.concluido)
        apply_status_change(
            db_session, ws, SpecWorkspaceStatus.arquivado, actor="joao@example.com"
        )
        assert ws.status == SpecWorkspaceStatus.arquivado
        assert ws.archived_at is not None
        assert ws.archived_by == "joao@example.com"

    def test_arquivar_direto_sem_passar_por_concluido_marca_completed_at_tambem(
        self, db_session
    ):
        """Arquivamento direto (sem concluido antes) também conta como conclusão."""
        ws = _mk_ws(db_session, status=SpecWorkspaceStatus.ativo)
        apply_status_change(
            db_session, ws, SpecWorkspaceStatus.arquivado, actor="system:auto-archive"
        )
        assert ws.completed_at is not None
        assert ws.archived_at is not None
        assert ws.archived_by == "system:auto-archive"

    def test_segundo_arquivamento_nao_sobrescreve_archived_at(self, db_session):
        ws = _mk_ws(db_session, status=SpecWorkspaceStatus.concluido)
        apply_status_change(db_session, ws, SpecWorkspaceStatus.arquivado, actor="a")
        first = ws.archived_at
        apply_status_change(db_session, ws, SpecWorkspaceStatus.arquivado, actor="b")
        assert ws.archived_at == first
        assert ws.archived_by == "a"


class TestReabertura:
    def test_reabrir_arquivado_para_ativo_limpa_timestamps(self, db_session):
        ws = _mk_ws(db_session, status=SpecWorkspaceStatus.concluido)
        apply_status_change(db_session, ws, SpecWorkspaceStatus.arquivado, actor="a")
        assert ws.archived_at is not None

        apply_status_change(db_session, ws, SpecWorkspaceStatus.ativo)
        assert ws.status == SpecWorkspaceStatus.ativo
        assert ws.completed_at is None
        assert ws.archived_at is None
        assert ws.archived_by is None

    def test_reabrir_concluido_para_planejamento_limpa_completed_at(self, db_session):
        ws = _mk_ws(db_session, status=SpecWorkspaceStatus.ativo)
        apply_status_change(db_session, ws, SpecWorkspaceStatus.concluido)
        assert ws.completed_at is not None

        apply_status_change(db_session, ws, SpecWorkspaceStatus.planejamento)
        assert ws.completed_at is None


class TestMirrorBestEffort:
    def test_chama_mirror_set_project_lifecycle_best_effort(self, db_session):
        ws = _mk_ws(db_session)
        with patch(
            "app.utils.planka_hooks.mirror_set_project_lifecycle_best_effort"
        ) as mirror:
            apply_status_change(db_session, ws, SpecWorkspaceStatus.concluido)
        mirror.assert_called_once_with(db_session, ws.id)

    def test_falha_no_espelho_nao_derruba_a_transicao(self, db_session):
        ws = _mk_ws(db_session)
        with patch(
            "app.utils.planka_hooks.mirror_set_project_lifecycle_best_effort",
            side_effect=RuntimeError("planka fora do ar"),
        ):
            result = apply_status_change(db_session, ws, SpecWorkspaceStatus.concluido)
        assert result.status == SpecWorkspaceStatus.concluido
