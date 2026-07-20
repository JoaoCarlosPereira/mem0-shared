"""Testes do router /api/v1/specs — workspaces e documentos (task_03).

Usa TestClient + override de get_db sobre SQLite em memória (padrão
``test_groups_router.py``). Cobre idempotência de workspace, conflito de versão
(409), autorização via AccessControl (403) e o painel agregado de Projeto.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import AccessControl, TaskCard, TaskCardStatus, SpecWorkspace
from app.routers.specs import router


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
def client(factory):
    app = FastAPI()
    app.include_router(router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _create_ws(client, project_id="mem0-shared", slug="ws-1", name="WS 1"):
    return client.post(
        "/api/v1/specs/workspaces",
        json={"project_id": project_id, "slug": slug, "name": name},
    )


class TestWorkspaceCrud:
    def test_cria_workspace(self, client):
        r = _create_ws(client)
        assert r.status_code == 201
        body = r.json()
        assert body["slug"] == "ws-1"
        assert body["status"] == "planejamento"

    def test_post_idempotente_por_project_slug(self, client, factory):
        first = _create_ws(client).json()
        r2 = _create_ws(client)
        assert r2.status_code == 200
        assert r2.json()["id"] == first["id"]

        s = factory()
        try:
            assert s.query(SpecWorkspace).count() == 1
        finally:
            s.close()

    def test_board_retorna_documentos_e_tasks(self, client):
        ws = _create_ws(client).json()
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "# PRD", "expected_version": None},
        )
        r = client.get(f"/api/v1/specs/workspaces/{ws['id']}")
        assert r.status_code == 200
        assert len(r.json()["documents"]) == 1
        assert r.json()["documents"][0]["document_type"] == "prd"

    def test_board_inexistente_404(self, client):
        r = client.get(f"/api/v1/specs/workspaces/{uuid.uuid4()}")
        assert r.status_code == 404


class TestDocumentVersioning:
    def test_grava_prd_v1_e_v2_e_lista_historico(self, client):
        ws = _create_ws(client).json()
        r1 = client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "# PRD v1", "expected_version": None},
        )
        assert r1.status_code == 200
        assert r1.json()["version"] == 1

        r2 = client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "# PRD v2", "expected_version": 1},
        )
        assert r2.status_code == 200
        assert r2.json()["version"] == 2

        hist = client.get(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd/versions"
        )
        assert hist.status_code == 200
        versions = hist.json()
        assert [v["version"] for v in versions] == [1, 2]

    def test_conflito_de_versao_retorna_409_com_conteudo_atual(self, client):
        ws = _create_ws(client).json()
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "v1", "expected_version": None},
        )
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "v2", "expected_version": 1},
        )
        # expected_version desatualizado
        r = client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "v-conflito", "expected_version": 1},
        )
        assert r.status_code == 409
        detail = r.json()["detail"]
        assert detail["conflict"] is True
        assert detail["current_version"] == 2
        assert detail["current_content"] == "v2"


class TestAccessControl:
    def test_sem_allow_recebe_403(self, client, factory):
        ws = _create_ws(client).json()
        ws_id = ws["id"]
        subject = uuid.uuid4()
        # Sujeito tem regra allow, mas para OUTRO workspace -> este fica inacessível.
        s = factory()
        try:
            s.add(
                AccessControl(
                    subject_type="user",
                    subject_id=subject,
                    object_type="spec_workspace",
                    object_id=uuid.uuid4(),
                    effect="allow",
                )
            )
            s.commit()
        finally:
            s.close()

        r = client.get(
            f"/api/v1/specs/workspaces/{ws_id}",
            params={"subject_type": "user", "subject_id": str(subject)},
        )
        assert r.status_code == 403

    def _add_rule(self, factory, subject, effect, object_id):
        s = factory()
        try:
            s.add(
                AccessControl(
                    subject_type="user",
                    subject_id=subject,
                    object_type="spec_workspace",
                    object_id=object_id,
                    effect=effect,
                )
            )
            s.commit()
        finally:
            s.close()

    def test_allow_all_sem_object_id_acessa(self, client, factory):
        ws_id = _create_ws(client).json()["id"]
        subject = uuid.uuid4()
        self._add_rule(factory, subject, "allow", None)  # allow-all
        r = client.get(
            f"/api/v1/specs/workspaces/{ws_id}",
            params={"subject_type": "user", "subject_id": str(subject)},
        )
        assert r.status_code == 200

    def test_deny_all_sem_object_id_recebe_403(self, client, factory):
        ws_id = _create_ws(client).json()["id"]
        subject = uuid.uuid4()
        self._add_rule(factory, subject, "deny", None)  # deny-all
        r = client.get(
            f"/api/v1/specs/workspaces/{ws_id}",
            params={"subject_type": "user", "subject_id": str(subject)},
        )
        assert r.status_code == 403

    def test_deny_especifico_remove_do_allow(self, client, factory):
        ws_id = _create_ws(client).json()["id"]
        subject = uuid.uuid4()
        self._add_rule(factory, subject, "allow", uuid.UUID(ws_id))
        self._add_rule(factory, subject, "deny", uuid.UUID(ws_id))
        r = client.get(
            f"/api/v1/specs/workspaces/{ws_id}",
            params={"subject_type": "user", "subject_id": str(subject)},
        )
        assert r.status_code == 403

    def test_com_allow_especifico_acessa(self, client, factory):
        ws = _create_ws(client).json()
        ws_id = ws["id"]
        subject = uuid.uuid4()
        s = factory()
        try:
            s.add(
                AccessControl(
                    subject_type="user",
                    subject_id=subject,
                    object_type="spec_workspace",
                    object_id=uuid.UUID(ws_id),
                    effect="allow",
                )
            )
            s.commit()
        finally:
            s.close()

        r = client.get(
            f"/api/v1/specs/workspaces/{ws_id}",
            params={"subject_type": "user", "subject_id": str(subject)},
        )
        assert r.status_code == 200


class TestProjectPanel:
    def test_painel_agrega_contagem_por_status(self, client, factory):
        ws1 = _create_ws(client, slug="ws-1").json()
        ws2 = _create_ws(client, slug="ws-2").json()

        s = factory()
        try:
            s.add_all(
                [
                    TaskCard(
                        workspace_id=uuid.UUID(ws1["id"]),
                        title="a",
                        status=TaskCardStatus.tasks,
                    ),
                    TaskCard(
                        workspace_id=uuid.UUID(ws1["id"]),
                        title="b",
                        status=TaskCardStatus.em_andamento,
                    ),
                    TaskCard(
                        workspace_id=uuid.UUID(ws2["id"]),
                        title="c",
                        status=TaskCardStatus.concluido,
                    ),
                ]
            )
            s.commit()
        finally:
            s.close()

        r = client.get("/api/v1/specs/projects/mem0-shared/workspaces")
        assert r.status_code == 200
        panel = {w["id"]: w["task_counts"] for w in r.json()}
        assert panel[ws1["id"]] == {"tasks": 1, "em_andamento": 1}
        assert panel[ws2["id"]] == {"concluido": 1}
