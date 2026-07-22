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


def _create_task(client, workspace_id, title="Card", **extra):
    body = {"workspace_id": workspace_id, "title": title, **extra}
    return client.post("/api/v1/specs/tasks", json=body)


class TestTaskLifecycle:
    def test_cria_task_nasce_em_tasks(self, client):
        ws = _create_ws(client).json()
        r = _create_task(client, ws["id"])
        assert r.status_code == 201
        assert r.json()["status"] == "tasks"
        assert r.json()["version"] == 1

    def test_claim_task_disponivel_200(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        r = client.post(
            f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "A"}
        )
        assert r.status_code == 200
        assert r.json()["assignee"] == "A"
        assert r.json()["status"] == "em_andamento"

    def test_board_enriquece_assignee_com_avatar(self, client, factory):
        from app.models import Machine, MachineStatus, User, USER_TYPE_PERSON

        s = factory()
        try:
            person = User(
                user_id="google-ana",
                google_sub="google-ana",
                display_name="Ana Silva",
                avatar_url="https://example.com/ana.png",
                user_type=USER_TYPE_PERSON,
            )
            s.add(person)
            s.flush()
            s.add(
                Machine(
                    hostname="host-a",
                    linked_user_id=person.id,
                    status=MachineStatus.linked,
                )
            )
            s.commit()
        finally:
            s.close()

        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        client.post(
            f"/api/v1/specs/tasks/{task['id']}/claim",
            json={"claimant": "host-a"},
        )
        board = client.get(f"/api/v1/specs/workspaces/{ws['id']}").json()
        claimed = next(t for t in board["tasks"] if t["id"] == task["id"])
        assert claimed["assignee"] == "host-a"
        assert claimed["assignee_display_name"] == "Ana Silva"
        assert claimed["assignee_avatar_url"] == "https://example.com/ana.png"

    def test_claim_task_ja_ativa_por_outro_409(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        client.post(f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "A"})
        r = client.post(
            f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "B"}
        )
        assert r.status_code == 409
        assert r.json()["detail"]["current_assignee"] == "A"

    def test_patch_status_transicao_invalida_422(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        r = client.patch(
            f"/api/v1/specs/tasks/{task['id']}/status",
            json={"new_status": "inexistente", "expected_version": 1},
        )
        assert r.status_code == 422

    def test_patch_status_conflito_de_versao_409(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        r = client.patch(
            f"/api/v1/specs/tasks/{task['id']}/status",
            json={"new_status": "revisao_codigo", "expected_version": 99},
        )
        assert r.status_code == 409

    def test_patch_bloqueio_sem_mudar_coluna(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        claimed = client.post(
            f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "A"}
        ).json()
        # is_blocked=true mantendo a coluna
        r = client.patch(
            f"/api/v1/specs/tasks/{task['id']}/status",
            json={
                "expected_version": claimed["version"],
                "is_blocked": True,
                "block_reason": "dependência",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "em_andamento"
        assert r.json()["is_blocked"] is True
        assert r.json()["block_reason"] == "dependência"

        # is_blocked=false limpa o marcador
        r2 = client.patch(
            f"/api/v1/specs/tasks/{task['id']}/status",
            json={"expected_version": r.json()["version"], "is_blocked": False},
        )
        assert r2.status_code == 200
        assert r2.json()["is_blocked"] is False
        assert r2.json()["block_reason"] is None

    def test_release_volta_para_tasks(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        client.post(f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "A"})
        r = client.post(
            f"/api/v1/specs/tasks/{task['id']}/release", json={"actor": "admin"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "tasks"
        assert r.json()["assignee"] is None


class TestComments:
    def test_comment_em_workspace(self, client):
        ws = _create_ws(client).json()
        r = client.post(
            "/api/v1/specs/comments",
            json={
                "target_type": "workspace",
                "target_id": ws["id"],
                "body": "olá",
                "author": "joao",
            },
        )
        assert r.status_code == 201
        assert r.json()["body"] == "olá"

    def test_comment_target_inexistente_404(self, client):
        r = client.post(
            "/api/v1/specs/comments",
            json={
                "target_type": "task",
                "target_id": str(uuid.uuid4()),
                "body": "x",
            },
        )
        assert r.status_code == 404


class TestEndToEndLifecycle:
    def test_ciclo_completo_de_tarefa(self, client, factory):
        from app.models import SpecAuditLog, TaskStatusHistory

        ws = _create_ws(client).json()
        # PRD v1
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "PRD v1", "expected_version": None},
        )
        # PRD v2 com expected_version errado -> 409
        bad = client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "PRD v2", "expected_version": 0},
        )
        assert bad.status_code == 409

        # cria task (nasce em tasks)
        task = _create_task(client, ws["id"]).json()
        assert task["status"] == "tasks"

        # claim ator A
        claimed = client.post(
            f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "A"}
        ).json()
        assert claimed["status"] == "em_andamento"

        # segunda tentativa por B -> 409, assignee continua A
        conflict = client.post(
            f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "B"}
        )
        assert conflict.status_code == 409

        # PATCH status para concluido (ator A)
        done = client.patch(
            f"/api/v1/specs/tasks/{task['id']}/status",
            json={
                "new_status": "concluido",
                "expected_version": claimed["version"],
                "actor": "A",
            },
        )
        assert done.status_code == 200
        assert done.json()["status"] == "concluido"

        # verifica histórico (2 entradas) e auditoria
        s = factory()
        try:
            hist = (
                s.query(TaskStatusHistory)
                .filter_by(task_id=uuid.UUID(task["id"]))
                .count()
            )
            audit = s.query(SpecAuditLog).count()
        finally:
            s.close()
        assert hist == 2  # tasks->em_andamento, em_andamento->concluido
        assert audit >= 3  # write_spec_document + claim_task + update_task_status


class TestAllWorkspacesIndex:
    def test_lista_todos_workspaces_de_todos_projetos(self, client):
        _create_ws(client, project_id="proj-a", slug="ws-a", name="A")
        _create_ws(client, project_id="proj-b", slug="ws-b", name="B")
        r = client.get("/api/v1/specs/workspaces")
        assert r.status_code == 200
        projs = {w["project_id"] for w in r.json()}
        assert projs == {"proj-a", "proj-b"}

    def test_indice_respeita_access_control(self, client, factory):
        ws = _create_ws(client, project_id="proj-a", slug="ws-a", name="A").json()
        _create_ws(client, project_id="proj-b", slug="ws-b", name="B")
        subject = uuid.uuid4()
        s = factory()
        try:
            # allow apenas para ws de proj-a -> índice só deve trazer esse.
            s.add(
                AccessControl(
                    subject_type="user",
                    subject_id=subject,
                    object_type="spec_workspace",
                    object_id=uuid.UUID(ws["id"]),
                    effect="allow",
                )
            )
            s.commit()
        finally:
            s.close()
        r = client.get(
            "/api/v1/specs/workspaces",
            params={"subject_type": "user", "subject_id": str(subject)},
        )
        assert r.status_code == 200
        assert [w["id"] for w in r.json()] == [ws["id"]]


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


class TestTaskAndDocumentMutation:
    def test_patch_task_metadata(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"], title="Old").json()
        r = client.patch(
            f"/api/v1/specs/tasks/{task['id']}",
            json={
                "expected_version": task["version"],
                "title": "New",
                "description": "Desc",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "New"
        assert body["description"] == "Desc"
        assert body["version"] == task["version"] + 1

    def test_patch_task_conflict_409(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        r = client.patch(
            f"/api/v1/specs/tasks/{task['id']}",
            json={"expected_version": 999, "title": "X"},
        )
        assert r.status_code == 409

    def test_delete_task(self, client):
        ws = _create_ws(client).json()
        task = _create_task(client, ws["id"]).json()
        r = client.delete(f"/api/v1/specs/tasks/{task['id']}")
        assert r.status_code == 204
        board = client.get(f"/api/v1/specs/workspaces/{ws['id']}").json()
        assert board["tasks"] == []

    def test_delete_document(self, client):
        ws = _create_ws(client).json()
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "# PRD", "author": "t"},
        )
        r = client.delete(f"/api/v1/specs/workspaces/{ws['id']}/documents/prd")
        assert r.status_code == 204
        board = client.get(f"/api/v1/specs/workspaces/{ws['id']}").json()
        assert board["documents"] == []

    def test_delete_workspace_remove_tudo_em_cascata(self, client, factory):
        from app.models import (
            SpecDocument,
            SpecDocumentVersion,
            SpecWorkspace,
            TaskCard,
        )

        ws = _create_ws(client).json()
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "v1", "expected_version": None},
        )
        client.put(
            f"/api/v1/specs/workspaces/{ws['id']}/documents/prd",
            json={"content": "v2", "expected_version": 1},
        )
        task = _create_task(client, ws["id"]).json()
        client.post(f"/api/v1/specs/tasks/{task['id']}/claim", json={"claimant": "A"})

        r = client.delete(f"/api/v1/specs/workspaces/{ws['id']}")
        assert r.status_code == 204

        s = factory()
        try:
            wsid = uuid.UUID(ws["id"])
            assert s.query(SpecWorkspace).filter_by(id=wsid).count() == 0
            assert s.query(SpecDocument).filter_by(workspace_id=wsid).count() == 0
            assert s.query(SpecDocumentVersion).count() == 0
            assert s.query(TaskCard).filter_by(workspace_id=wsid).count() == 0
        finally:
            s.close()

    def test_delete_workspace_inexistente_404(self, client):
        assert (
            client.delete(f"/api/v1/specs/workspaces/{uuid.uuid4()}").status_code == 404
        )

    def test_delete_workspace_nao_afeta_outra(self, client, factory):
        from app.models import SpecWorkspace

        keep = _create_ws(client, slug="fica", name="Fica").json()
        drop = _create_ws(client, slug="sai", name="Sai").json()
        _create_task(client, keep["id"])

        assert client.delete(f"/api/v1/specs/workspaces/{drop['id']}").status_code == 204
        s = factory()
        try:
            assert s.query(SpecWorkspace).filter_by(id=uuid.UUID(keep["id"])).count() == 1
            assert s.query(SpecWorkspace).filter_by(id=uuid.UUID(drop["id"])).count() == 0
        finally:
            s.close()
