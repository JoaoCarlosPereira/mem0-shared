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
from app.utils import project_groups, spec_search
from app.utils.spec_search import (
    index_completed_workspace,
    index_document_now,
    search_specs,
)


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

    def test_only_completed_false_indexa_em_andamento(self, factory):
        """Spec em andamento precisa entrar no indice; e quando descobri-la importa."""
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.ativo)
            _add_doc(db, ws, DocumentType.prd, "# PRD")
            vs = FakeVectorStore()
            count = index_completed_workspace(
                db, ws, embedder=FakeEmbedder(), vector_store=vs, only_completed=False
            )
            assert count == 1
            assert vs.inserted[0]["payloads"][0]["workspace_status"] == "ativo"
        finally:
            db.close()


class TestIndexDocumentNow:
    def test_indexa_documento_de_workspace_em_andamento(self, factory):
        db = factory()
        try:
            ws = _mk_ws(db, status=SpecWorkspaceStatus.ativo)
            doc = _add_doc(db, ws, DocumentType.prd, "# PRD")
            vs = FakeVectorStore()

            assert index_document_now(
                db, ws, doc, embedder=FakeEmbedder(), vector_store=vs
            )
            payload = vs.inserted[0]["payloads"][0]
            assert payload["workspace_status"] == "ativo"
            assert payload["document_type"] == "prd"
        finally:
            db.close()

    def test_documento_vazio_nao_indexa(self, factory):
        db = factory()
        try:
            ws = _mk_ws(db)
            doc = SpecDocument(
                workspace_id=ws.id, document_type=DocumentType.prd, current_content=None
            )
            db.add(doc)
            db.commit()
            vs = FakeVectorStore()
            assert not index_document_now(
                db, ws, doc, embedder=FakeEmbedder(), vector_store=vs
            )
            assert vs.inserted == []
        finally:
            db.close()

    def test_falha_de_indexacao_nao_propaga(self, factory):
        """O dado ja esta no Postgres; o indice e derivado e nao pode derrubar a escrita."""
        db = factory()
        try:
            ws = _mk_ws(db)
            doc = _add_doc(db, ws, DocumentType.prd, "# PRD")

            class Explode:
                def insert(self, *a, **k):
                    raise RuntimeError("qdrant fora do ar")

            assert not index_document_now(
                db, ws, doc, embedder=FakeEmbedder(), vector_store=Explode()
            )
        finally:
            db.close()


class TestSearchFamiliaDeProjeto:
    """Busca de specs com MEM0_PROJECT_GROUPS.

    Uma feature atravessa repositorios, mas o project_id segue o diretorio de
    trabalho. Antes, buscar de sysmovs nao achava a spec gravada sob
    sysmos1-modular: o filtro do Qdrant e o pos-filtro exigiam nome EXATO, e o
    boost de familia de rank_search_results rodava depois do descarte.
    """

    GRUPOS = "sysmo-s1=sysmovs,sysmos1-modular,db-sysmo-s1"

    @pytest.fixture(autouse=True)
    def _limpa(self):
        project_groups.reset_project_group_cache()
        yield
        project_groups.reset_project_group_cache()

    def _hits(self):
        return [
            FakeHit("irmao", 0.9, {"data": "a", "project": "sysmos1-modular"}),
            FakeHit("proprio", 0.8, {"data": "b", "project": "sysmovs"}),
            FakeHit("alheio", 0.7, {"data": "c", "project": "ms-dashboard-s1"}),
        ]

    def test_irmao_da_familia_aparece(self, monkeypatch):
        monkeypatch.setenv("MEM0_PROJECT_GROUPS", self.GRUPOS)
        project_groups.reset_project_group_cache()

        r = search_specs(
            "x",
            project_id="sysmovs",
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(self._hits()),
        )

        assert {h["id"] for h in r} == {"irmao", "proprio"}

    def test_projeto_de_fora_da_familia_continua_excluido(self, monkeypatch):
        monkeypatch.setenv("MEM0_PROJECT_GROUPS", self.GRUPOS)
        project_groups.reset_project_group_cache()

        r = search_specs(
            "x",
            project_id="sysmovs",
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(self._hits()),
        )

        assert "alheio" not in {h["id"] for h in r}

    def test_filtro_do_qdrant_pede_a_familia_inteira(self, monkeypatch):
        """O irmao precisa VOLTAR da busca; filtrar so no pos-filtro nao basta."""
        monkeypatch.setenv("MEM0_PROJECT_GROUPS", self.GRUPOS)
        project_groups.reset_project_group_cache()
        vs = FakeVectorStore(self._hits())
        capturado = {}

        def _search(query, vectors, top_k=5, filters=None):
            capturado["filters"] = filters
            return vs._hits

        vs.search = _search
        search_specs("x", project_id="sysmovs", embedder=FakeEmbedder(), vector_store=vs)

        assert set(capturado["filters"]["project_id"]["in"]) == {
            "sysmo-s1",
            "sysmovs",
            "sysmos1-modular",
            "db-sysmo-s1",
        }

    def test_sem_familia_configurada_mantem_nome_exato(self, monkeypatch):
        """Comportamento anterior preservado para quem nao usa grupos."""
        monkeypatch.delenv("MEM0_PROJECT_GROUPS", raising=False)
        project_groups.reset_project_group_cache()
        vs = FakeVectorStore(self._hits())
        capturado = {}

        def _search(query, vectors, top_k=5, filters=None):
            capturado["filters"] = filters
            return vs._hits

        vs.search = _search
        r = search_specs("x", project_id="sysmovs", embedder=FakeEmbedder(), vector_store=vs)

        assert capturado["filters"] == {"project_id": "sysmovs"}
        assert {h["id"] for h in r} == {"proprio"}

    def test_projeto_sem_grupo_nao_vira_familia(self, monkeypatch):
        monkeypatch.setenv("MEM0_PROJECT_GROUPS", self.GRUPOS)
        project_groups.reset_project_group_cache()
        vs = FakeVectorStore(self._hits())
        capturado = {}

        def _search(query, vectors, top_k=5, filters=None):
            capturado["filters"] = filters
            return vs._hits

        vs.search = _search
        search_specs(
            "x", project_id="ms-dashboard-s1", embedder=FakeEmbedder(), vector_store=vs
        )

        assert capturado["filters"] == {"project_id": "ms-dashboard-s1"}

    def test_sem_project_id_nao_filtra(self, monkeypatch):
        monkeypatch.setenv("MEM0_PROJECT_GROUPS", self.GRUPOS)
        project_groups.reset_project_group_cache()
        vs = FakeVectorStore(self._hits())
        capturado = {}

        def _search(query, vectors, top_k=5, filters=None):
            capturado["filters"] = filters
            return vs._hits

        vs.search = _search
        r = search_specs("x", embedder=FakeEmbedder(), vector_store=vs)

        assert capturado["filters"] is None
        assert len(r) == 3


class TestSearchStatuses:
    def _hits(self):
        return [
            FakeHit("c", 0.9, {"data": "concluida", "workspace_status": "concluido"}),
            FakeHit("a", 0.8, {"data": "em andamento", "workspace_status": "ativo"}),
            FakeHit("legado", 0.7, {"data": "sem o campo"}),
        ]

    def test_padrao_so_concluido(self):
        """Comportamento anterior preservado para quem nao pede nada."""
        results = search_specs(
            "x", embedder=FakeEmbedder(), vector_store=FakeVectorStore(self._hits())
        )
        assert {r["id"] for r in results} == {"c", "legado"}

    def test_ponto_legado_sem_campo_conta_como_concluido(self):
        """Antes, indexar so acontecia em concluido - logo, legado e concluido."""
        results = search_specs(
            "x", embedder=FakeEmbedder(), vector_store=FakeVectorStore(self._hits())
        )
        assert "legado" in {r["id"] for r in results}

    def test_status_explicito_alcanca_trabalho_em_andamento(self):
        results = search_specs(
            "x",
            statuses=["ativo"],
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(self._hits()),
        )
        assert {r["id"] for r in results} == {"a"}

    def test_asterisco_traz_todos(self):
        results = search_specs(
            "x",
            statuses=["*"],
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(self._hits()),
        )
        assert {r["id"] for r in results} == {"c", "a", "legado"}

    def test_lista_vazia_equivale_a_todos(self):
        results = search_specs(
            "x",
            statuses=[],
            embedder=FakeEmbedder(),
            vector_store=FakeVectorStore(self._hits()),
        )
        assert len(results) == 3


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
    """Busca semântica com isolamento por grupo (kanban-board-group-isolation).

    O endpoint devolve apenas hits cujo ``workspace_id`` pertence a um workspace
    do grupo do usuário autenticado (fail-closed: sem grupo => vazio).
    """

    @pytest.fixture
    def client(self, factory, monkeypatch):
        import uuid
        from app.models import DEFAULT_GROUP_NAME, Group, User, SpecWorkspace
        from app.routers.specs import router
        from app.utils.logging_context import auth_method_var, auth_user_var

        app = FastAPI()
        app.include_router(router)

        # Usuário autenticado no Default group + 2 workspaces do mesmo grupo.
        s = factory()
        try:
            g = s.query(Group).filter(Group.name == DEFAULT_GROUP_NAME).first()
            if not g:
                g = Group(name=DEFAULT_GROUP_NAME)
                s.add(g)
                s.flush()
            user = User(id=uuid.uuid4(), user_id="search-user", group_id=g.id, user_type="person")
            ws_a = SpecWorkspace(project_id="mem0-shared", slug="ws-a", name="A", group_id=g.id)
            ws_b = SpecWorkspace(project_id="outro", slug="ws-b", name="B", group_id=g.id)
            s.add_all([user, ws_a, ws_b])
            s.commit()
            s.refresh(ws_a)
            s.refresh(ws_b)
            ws_a_id, ws_b_id, user_id = str(ws_a.id), str(ws_b.id), str(user.id)
        finally:
            s.close()

        def _override():
            s = factory()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override
        tok_m = auth_method_var.set("session")
        tok_u = auth_user_var.set(user_id)

        hits = [
            FakeHit("1", 0.9, {"data": "spec A", "project": "mem0-shared", "document_type": "prd", "workspace_id": ws_a_id}),
            FakeHit("2", 0.8, {"data": "spec B", "project": "outro", "document_type": "prd", "workspace_id": ws_b_id}),
        ]

        class FakeClient:
            embedding_model = FakeEmbedder()

        monkeypatch.setattr(spec_search, "get_memory_client_safe", lambda: FakeClient())
        monkeypatch.setattr(spec_search, "get_specs_vector_store", lambda base=None: FakeVectorStore(hits))
        try:
            yield TestClient(app)
        finally:
            auth_user_var.reset(tok_u)
            auth_method_var.reset(tok_m)

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

    def test_search_legacy_sem_grupo_retorna_specs(self, factory, monkeypatch):
        """Modo legado sem Google compartilha specs mesmo sem vínculo de grupo."""
        from app.routers.specs import router
        from app.utils.logging_context import auth_method_var, auth_user_var

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
        ]

        class FakeClient:
            embedding_model = FakeEmbedder()

        monkeypatch.setattr(spec_search, "get_memory_client_safe", lambda: FakeClient())
        monkeypatch.setattr(spec_search, "get_specs_vector_store", lambda base=None: FakeVectorStore(hits))

        tok_m = auth_method_var.set("legacy")
        tok_u = auth_user_var.set("")
        try:
            r = TestClient(app).get("/api/v1/specs/search", params={"q": "spec"})
            assert r.status_code == 200
            assert [item["id"] for item in r.json()] == ["1"]
        finally:
            auth_user_var.reset(tok_u)
            auth_method_var.reset(tok_m)
