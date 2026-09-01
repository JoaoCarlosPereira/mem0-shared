"""Testes da task_08 (shared-specs): tools MCP de tasks e comentários.

Mesmo padrão de ``test_mcp_specs.py``. Cobrem a exclusividade de claim via MCP,
transições de status inválidas (erro estruturado, não exceção) e comentários com
alvo inexistente.
"""

import json
import os
import uuid

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_server
from app.database import Base
from app.mcp_server import (
    add_spec_comment,
    claim_task,
    create_spec_workspace,
    create_task,
    get_task,
    release_task,
    update_task_status,
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


@pytest.fixture(autouse=True)
def _wire(factory, monkeypatch):
    monkeypatch.setattr(mcp_server, "SessionLocal", factory)
    
    from app.utils.logging_context import auth_method_var, machine_var
    auth_method_var.set("legacy")
    machine_var.set("DESKTOP-01")

    # Manually provision the user in the factory
    s = factory()
    try:
        from app.models import DEFAULT_GROUP_NAME, Group, User
        g = s.query(Group).filter(Group.name == DEFAULT_GROUP_NAME).first()
        if not g:
            g = Group(name=DEFAULT_GROUP_NAME)
            s.add(g)
            s.flush()
        u = s.query(User).filter(User.user_id == "DESKTOP-01").first()
        if not u:
            import uuid
            s.add(User(id=uuid.uuid4(), user_id="DESKTOP-01", group_id=g.id, user_type="legacy_host"))
        s.commit()
    finally:
        s.close()

    mcp_server.user_id_var.set("DESKTOP-01")
    mcp_server.client_name_var.set("cursor")
    mcp_server.auth_method_var.set("legacy")
    mcp_server.auth_user_var.set("")
    yield


async def _mk_ws_and_task(title="Card"):
    ws = json.loads(await create_spec_workspace("mem0-shared", "ws-1", "WS 1"))
    task = json.loads(await create_task(ws["id"], title))
    return ws, task


class TestCreateAndClaim:
    @pytest.mark.asyncio
    async def test_create_task_nasce_em_tasks(self):
        _, task = await _mk_ws_and_task()
        assert task["status"] == "tasks"
        assert task["version"] == 1

    @pytest.mark.asyncio
    async def test_claim_bem_sucedido(self):
        _, task = await _mk_ws_and_task()
        out = json.loads(await claim_task(task["id"]))
        assert out["claimed"] is True
        assert out["assignee"] == "DESKTOP-01"
        assert out["version"] == 2

    @pytest.mark.asyncio
    async def test_claim_exclusividade_via_mcp(self, monkeypatch):
        _, task = await _mk_ws_and_task()
        # Agente A assume
        mcp_server.user_id_var.set("host-a")
        first = json.loads(await claim_task(task["id"]))
        assert first["claimed"] is True

        # Agente B tenta assumir a mesma task -> falha estruturada
        mcp_server.user_id_var.set("host-b")
        second = json.loads(await claim_task(task["id"]))
        assert second["claimed"] is False
        assert second["current_assignee"] == "host-a"
        assert "message" in second

    @pytest.mark.asyncio
    async def test_claim_task_inexistente_error(self):
        out = await claim_task(str(uuid.uuid4()))
        assert out.startswith("Error:")

    @pytest.mark.asyncio
    async def test_legacy_get_e_claim_ignoram_grupo_e_acl(self, factory):
        from app.models import AccessControl, Group, SpecWorkspace, TaskCard

        workspace_id = uuid.uuid4()
        task_id = uuid.uuid4()
        s = factory()
        try:
            other_group = Group(name="Grupo isolado")
            s.add(other_group)
            s.flush()
            s.add(
                SpecWorkspace(
                    id=workspace_id,
                    project_id="outro-projeto",
                    slug="workspace-isolado",
                    name="Workspace isolado",
                    group_id=other_group.id,
                )
            )
            s.add(TaskCard(id=task_id, workspace_id=workspace_id, title="Task compartilhada"))
            s.add(
                AccessControl(
                    subject_type="user",
                    subject_id=None,
                    object_type="spec_workspace",
                    object_id=None,
                    effect="deny",
                )
            )
            s.commit()
        finally:
            s.close()

        task = json.loads(await get_task(str(task_id)))
        assert task["title"] == "Task compartilhada"
        claimed = json.loads(await claim_task(str(task_id)))
        assert claimed["claimed"] is True


class TestReleaseAndStatus:
    @pytest.mark.asyncio
    async def test_release_volta_para_tasks(self):
        _, task = await _mk_ws_and_task()
        await claim_task(task["id"])
        out = json.loads(await release_task(task["id"]))
        assert out["released"] is True

    @pytest.mark.asyncio
    async def test_update_status_valido(self):
        _, task = await _mk_ws_and_task()
        claimed = json.loads(await claim_task(task["id"]))
        out = json.loads(
            await update_task_status(task["id"], "revisao_codigo", claimed["version"])
        )
        assert out["updated"] is True
        assert out["status"] == "revisao_codigo"

    @pytest.mark.asyncio
    async def test_update_status_transicao_invalida_erro_estruturado(self):
        _, task = await _mk_ws_and_task()
        out = json.loads(await update_task_status(task["id"], "inexistente", 1))
        assert "error" in out
        assert "valid" in out
        assert "em_andamento" in out["valid"]

    @pytest.mark.asyncio
    async def test_update_status_conflito_de_versao(self):
        _, task = await _mk_ws_and_task()
        claimed = json.loads(await claim_task(task["id"]))
        out = json.loads(
            await update_task_status(task["id"], "revisao_codigo", 99)
        )
        assert out["conflict"] is True
        assert claimed["version"] == 2

    @pytest.mark.asyncio
    async def test_update_status_sem_claim_rejeitado(self):
        _, task = await _mk_ws_and_task()
        out = json.loads(
            await update_task_status(task["id"], "em_andamento", 1)
        )
        assert out.get("policy") is True
        assert out["code"] == "use_claim"

    @pytest.mark.asyncio
    async def test_reportar_bloqueio_mantendo_status(self):
        _, task = await _mk_ws_and_task()
        claimed = json.loads(await claim_task(task["id"]))
        out = json.loads(
            await update_task_status(
                task["id"],
                "em_andamento",
                claimed["version"],
                is_blocked=True,
                block_reason="dep externa",
            )
        )
        assert out["updated"] is True
        assert out["status"] == "em_andamento"


class TestComments:
    @pytest.mark.asyncio
    async def test_add_comment_em_task(self):
        _, task = await _mk_ws_and_task()
        out = json.loads(await add_spec_comment("task", task["id"], "comentário"))
        assert out["body"] == "comentário"
        assert out["author"] == "DESKTOP-01"

    @pytest.mark.asyncio
    async def test_add_comment_com_agent_token_preserva_pessoa_autenticada(self, factory):
        _, task = await _mk_ws_and_task()
        # Cria um usuário real no Default group (necessário para o isolamento por grupo).
        s = factory()
        try:
            from app.models import DEFAULT_GROUP_NAME, Group, User
            g = s.query(Group).filter(Group.name == DEFAULT_GROUP_NAME).first()
            person = User(id=uuid.uuid4(), user_id="agent-person", group_id=g.id, user_type="person")
            s.add(person)
            s.commit()
            person_id = str(person.id)
        finally:
            s.close()
        # Sem máquina vinculada: o autor deve ser a pessoa autenticada, não o host.
        mcp_server.auth_method_var.set("agent_token")
        mcp_server.auth_user_var.set(person_id)
        mcp_server.machine_var.set("")

        out = json.loads(await add_spec_comment("task", task["id"], "comentário"))

        assert out["author"] == person_id

    @pytest.mark.asyncio
    async def test_add_comment_target_inexistente_error(self):
        out = await add_spec_comment("task", str(uuid.uuid4()), "x")
        assert out.startswith("Error:")

    @pytest.mark.asyncio
    async def test_add_comment_target_type_invalido_error(self):
        out = await add_spec_comment("tipo_invalido", str(uuid.uuid4()), "x")
        assert out.startswith("Error:")
