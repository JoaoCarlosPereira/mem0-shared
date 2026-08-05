"""Testes de ``POST /planka/project-lifecycle`` (Tarefa kanban-archive-lifecycle).

Bridge PLANKA → Spec: traduz o clique de "Arquivar"/"Concluir" no board PLANKA
de volta para ``SpecWorkspace.status``. Mesma convenção de fixtures de
``test_planka_bridge.py`` (TestClient + factory própria, ``PLANKA_MIRROR_SYNC``
desligado para não depender de sidecar real).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Project, SpecPlankaIdMap, SpecWorkspace, SpecWorkspaceStatus
from app.routers.specs import router as specs_router
from app.utils.planka import ENTITY_PROJECT


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


@pytest.fixture
def bridge_client(factory, monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    monkeypatch.setenv("PLANKA_INTERNAL_ACCESS_TOKEN", "bridge-secret")
    monkeypatch.delenv("INTERNAL_ACCESS_TOKEN", raising=False)

    app = FastAPI()
    app.include_router(specs_router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app), factory


def _mk_mapped_workspace(db, *, status=SpecWorkspaceStatus.ativo, planka_project_id="pproj-1"):
    if not db.query(Project).filter(Project.name == "mem0-shared").first():
        db.add(Project(name="mem0-shared"))
        db.commit()
    ws = SpecWorkspace(
        project_id="mem0-shared", slug="project-lifecycle-ws", name="Lifecycle", status=status
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    db.add(SpecPlankaIdMap(entity_type=ENTITY_PROJECT, spec_id=ws.id, planka_id=planka_project_id))
    db.commit()
    return ws


class TestProjectLifecycleEndpoint:
    def test_archives_mapped_workspace(self, bridge_client):
        client, factory = bridge_client
        db = factory()
        try:
            ws = _mk_mapped_workspace(db, status=SpecWorkspaceStatus.concluido)
            ws_id = ws.id
        finally:
            db.close()

        resp = client.post(
            "/api/v1/specs/planka/project-lifecycle",
            headers={"authorization": "Bearer bridge-secret"},
            json={
                "planka_project_id": "pproj-1",
                "is_archived": True,
                "is_completed": True,
                "actor": "joao@example.com",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is True
        assert body["status"] == "arquivado"

        db = factory()
        try:
            fresh = db.query(SpecWorkspace).filter_by(id=ws_id).one()
            assert fresh.status == SpecWorkspaceStatus.arquivado
            assert fresh.archived_by == "joao@example.com"
        finally:
            db.close()

    def test_marks_completed_without_archiving(self, bridge_client):
        client, factory = bridge_client
        db = factory()
        try:
            _mk_mapped_workspace(db, status=SpecWorkspaceStatus.ativo, planka_project_id="pproj-2")
        finally:
            db.close()

        resp = client.post(
            "/api/v1/specs/planka/project-lifecycle",
            headers={"authorization": "Bearer bridge-secret"},
            json={
                "planka_project_id": "pproj-2",
                "is_archived": False,
                "is_completed": True,
                "actor": "joao@example.com",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "concluido"

    def test_unarchiving_reopens_to_ativo(self, bridge_client):
        client, factory = bridge_client
        db = factory()
        try:
            _mk_mapped_workspace(
                db, status=SpecWorkspaceStatus.arquivado, planka_project_id="pproj-3"
            )
        finally:
            db.close()

        resp = client.post(
            "/api/v1/specs/planka/project-lifecycle",
            headers={"authorization": "Bearer bridge-secret"},
            json={
                "planka_project_id": "pproj-3",
                "is_archived": False,
                "is_completed": False,
                "actor": "joao@example.com",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ativo"

    def test_unmapped_project_is_skipped(self, bridge_client):
        client, _factory = bridge_client
        resp = client.post(
            "/api/v1/specs/planka/project-lifecycle",
            headers={"authorization": "Bearer bridge-secret"},
            json={
                "planka_project_id": "unknown-project",
                "is_archived": True,
                "is_completed": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] is False
        assert body["skipped"] is True

    def test_rejects_wrong_bridge_token(self, bridge_client):
        client, _ = bridge_client
        resp = client.post(
            "/api/v1/specs/planka/project-lifecycle",
            headers={"authorization": "Bearer wrong-token"},
            json={
                "planka_project_id": "pproj-1",
                "is_archived": True,
                "is_completed": True,
            },
        )
        assert resp.status_code == 401

    def test_rejects_missing_authorization(self, bridge_client):
        client, _ = bridge_client
        resp = client.post(
            "/api/v1/specs/planka/project-lifecycle",
            json={
                "planka_project_id": "pproj-1",
                "is_archived": True,
                "is_completed": True,
            },
        )
        assert resp.status_code == 401
