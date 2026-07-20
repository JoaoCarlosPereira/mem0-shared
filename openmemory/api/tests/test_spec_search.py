"""Testes da task_06 (shared-specs): indexação e busca semântica de specs.

Client Qdrant/embedder mockados. Cobrem o gatilho de indexação (só em
``concluido``), o payload indexado e o boost de grupo/filtro de projeto na busca
(ADR-006).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import (
    DocumentType,
    Project,
    SpecDocument,
    SpecWorkspace,
    SpecWorkspaceStatus,
)
from app.utils import spec_search
from app.utils.spec_search import index_completed_workspace, search_specs


class FakeEmbedder:
    def embed(self, text, mode):
        return [0.1, 0.2, 0.3]


class FakeHit:
    def __init__(self, id, score, payload):
        self.id = id
        self.score = score
        self.payload = payload


class FakeVectorStore:
    def __init__(self, hits=None):
        self.inserted = []
        self._hits = hits or []

    def insert(self, vectors, payloads, ids):
        self.inserted.append({"vectors": vectors, "payloads": payloads, "ids": ids})

    def search(self, query, vectors, top_k=5, filters=None):
        return self._hits


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


def _mk_ws(db, status=SpecWorkspaceStatus.ativo, created_by="DESKTOP-01"):
    db.add(Project(name="mem0-shared"))
    db.commit()
    ws = SpecWorkspace(
        project_id="mem0-shared", slug="ws-1", name="WS", status=status, created_by=created_by
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _add_doc(db, ws, doc_type, content):
    doc = SpecDocument(
        workspace_id=ws.id, document_type=doc_type, current_version=1, current_content=content
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


class TestIndexTrigger:
    def test_nao_indexa_workspace_nao_concluido(self, factory):
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.ativo)
            _add_doc(db, ws, DocumentType.prd, "# PRD")
            vs = FakeVectorStore()
            count = index_completed_workspace(
                db, ws, embedder=FakeEmbedder(), vector_store=vs
            )
            assert count == 0
            assert vs.inserted == []
        finally:
            db.close()

    def test_indexa_cada_documento_quando_concluido(self, factory):
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.concluido)
            _add_doc(db, ws, DocumentType.prd, "# PRD")
            _add_doc(db, ws, DocumentType.techspec, "# TechSpec")
            vs = FakeVectorStore()
            count = index_completed_workspace(
                db, ws, embedder=FakeEmbedder(), vector_store=vs
            )
            assert count == 2
            assert len(vs.inserted) == 2
        finally:
            db.close()

    def test_payload_inclui_campos_obrigatorios(self, factory):
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.concluido)
            _add_doc(db, ws, DocumentType.prd, "# PRD")
            vs = FakeVectorStore()
            index_completed_workspace(db, ws, embedder=FakeEmbedder(), vector_store=vs)
            payload = vs.inserted[0]["payloads"][0]
            assert payload["project_id"] == "mem0-shared"
            assert payload["workspace_id"] == str(ws.id)
            assert payload["document_type"] == "prd"
            assert "group_id" in payload
        finally:
            db.close()

    def test_backend_indisponivel_nao_indexa(self, factory, monkeypatch):
        monkeypatch.setattr(spec_search, "get_memory_client_safe", lambda: None)
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.concluido)
            _add_doc(db, ws, DocumentType.prd, "# PRD")
            assert index_completed_workspace(db, ws) == 0
        finally:
            db.close()

    def test_reset_specs_vector_store(self, monkeypatch):
        spec_search._specs_vector_store = object()
        spec_search.reset_specs_vector_store()
        assert spec_search._specs_vector_store is None

    def test_documento_sem_conteudo_e_ignorado(self, factory):
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.concluido)
            doc = SpecDocument(
                workspace_id=ws.id, document_type=DocumentType.prd, current_content=None
            )
            db.add(doc)
            db.commit()
            vs = FakeVectorStore()
            assert index_completed_workspace(db, ws, embedder=FakeEmbedder(), vector_store=vs) == 0
        finally:
            db.close()


class TestSearch:
    def test_filtra_por_projeto(self):
        hits = [
            FakeHit("1", 0.9, {"data": "a", "project": "mem0-shared", "document_type": "prd"}),
            FakeHit("2", 0.8, {"data": "b", "project": "outro", "document_type": "prd"}),
        ]
        results = search_specs(
            "x",
            project_id="mem0-shared",
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(hits),
        )
        assert [r["id"] for r in results] == ["1"]

    def test_boost_de_grupo_reordena(self, monkeypatch):
        # Resultado de menor score, mas do mesmo grupo, deve subir (SEARCH_GROUP_BOOST).
        import app.utils.recency as recency

        monkeypatch.setattr(
            recency,
            "group_of_hostname",
            lambda owner: {"host-a": "eng", "host-b": "outro"}.get(owner),
        )
        hits = [
            FakeHit("b", 0.9, {"data": "b", "project": "p", "owner": "host-b"}),
            FakeHit("a", 0.5, {"data": "a", "project": "p", "owner": "host-a"}),
        ]
        results = search_specs(
            "x",
            requester_group="eng",
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(hits),
        )
        # host-a (score 0.5 * 2.5 = 1.25) supera host-b (0.9)
        assert results[0]["id"] == "a"

    def test_backend_indisponivel_retorna_vazio(self, monkeypatch):
        monkeypatch.setattr(spec_search, "get_memory_client_safe", lambda: None)
        assert search_specs("x") == []


class TestSearchEndpoint:
    @pytest.fixture
    def client(self, factory, monkeypatch):
        from app.routers.specs import router

        app = FastAPI()
        app.include_router(router)

        def _override():
            s = factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override

        hits = [
            FakeHit("1", 0.9, {"data": "spec A", "project": "mem0-shared", "document_type": "prd"}),
            FakeHit("2", 0.8, {"data": "spec B", "project": "outro", "document_type": "prd"}),
        ]

        class FakeClient:
            embedding_model = FakeEmbedder()

        monkeypatch.setattr(spec_search, "get_memory_client_safe", lambda: FakeClient())
        monkeypatch.setattr(spec_search, "get_specs_vector_store", lambda base=None: FakeVectorStore(hits))
        return TestClient(app)

    def test_search_filtra_por_projeto(self, client):
        r = client.get("/api/v1/specs/search", params={"q": "spec", "project_id": "mem0-shared"})
        assert r.status_code == 200
        body = r.json()
        assert [x["id"] for x in body] == ["1"]
        assert body[0]["content"] == "spec A"

    def test_search_sem_filtro_retorna_todos(self, client):
        r = client.get("/api/v1/specs/search", params={"q": "spec"})
        assert r.status_code == 200
        assert len(r.json()) == 2
