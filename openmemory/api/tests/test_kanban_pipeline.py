"""Testes do guia de pipeline Kanban e rejeição de skip."""

import json
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_server
from app.database import Base
from app.mcp_server import claim_task, create_spec_workspace, create_task, update_task_status
from app.models import TaskCardStatus
from app.utils.kanban_pipeline import KanbanSkipError, assert_no_forward_skip, guide_for


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

    # Ator DESKTOP-01: alinha auth_method/machine_var e provisiona o usuário
    # no Default group dentro da factory (SessionLocal do teste em memória).
    from app.utils.logging_context import auth_method_var, machine_var
    auth_method_var.set("legacy")
    machine_var.set("DESKTOP-01")

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
            s.add(User(id=__import__("uuid").uuid4(), user_id="DESKTOP-01", group_id=g.id, user_type="legacy_host"))
        s.commit()
    finally:
        s.close()

    mcp_server.user_id_var.set("DESKTOP-01")
    mcp_server.client_name_var.set("cursor")
    mcp_server.auth_method_var.set("legacy")
    mcp_server.auth_user_var.set("")
    yield


def test_guide_em_andamento_aponta_revisao():
    g = guide_for("em_andamento")
    assert g["next_column"] == "revisao_codigo"
    assert "revisao_codigo" in g["do_now"]
    assert g["next_action"] == "update_task_status"


def test_skip_em_andamento_para_concluido_rejeitado():
    with pytest.raises(KanbanSkipError) as ei:
        assert_no_forward_skip(
            TaskCardStatus.em_andamento, TaskCardStatus.concluido
        )
    assert ei.value.code == "skip_pipeline"


def test_avanco_uma_coluna_ok():
    assert_no_forward_skip(
        TaskCardStatus.em_andamento, TaskCardStatus.revisao_codigo
    )
    assert_no_forward_skip(
        TaskCardStatus.revisao_codigo, TaskCardStatus.fase_teste
    )


def test_retrocesso_ok():
    assert_no_forward_skip(
        TaskCardStatus.fase_teste, TaskCardStatus.em_andamento
    )


@pytest.mark.asyncio
async def test_claim_mcp_inclui_kanban_do_now():
    ws = json.loads(await create_spec_workspace("mem0-shared", "ws-k", "WS K"))
    task = json.loads(await create_task(ws["id"], "Card K"))
    out = json.loads(await claim_task(task["id"]))
    assert out["claimed"] is True
    assert out["status"] == "em_andamento"
    assert out["kanban"]["column"] == "em_andamento"
    assert out["kanban"]["next_column"] == "revisao_codigo"
    assert "do_now" in out["kanban"]


@pytest.mark.asyncio
async def test_mcp_rejeita_pulo_para_concluido():
    ws = json.loads(await create_spec_workspace("mem0-shared", "ws-k2", "WS K2"))
    task = json.loads(await create_task(ws["id"], "Card K2"))
    claimed = json.loads(await claim_task(task["id"]))
    out = json.loads(
        await update_task_status(task["id"], "concluido", claimed["version"])
    )
    assert out.get("policy") is True
    assert out["code"] == "skip_pipeline"


@pytest.mark.asyncio
async def test_mcp_pipeline_completo_com_guias():
    ws = json.loads(await create_spec_workspace("mem0-shared", "ws-k3", "WS K3"))
    task = json.loads(await create_task(ws["id"], "Card K3"))
    v = json.loads(await claim_task(task["id"]))["version"]
    r = json.loads(await update_task_status(task["id"], "revisao_codigo", v))
    assert r["updated"] and r["kanban"]["next_column"] == "fase_teste"
    t = json.loads(await update_task_status(task["id"], "fase_teste", r["version"]))
    assert t["kanban"]["next_column"] == "concluido"
    c = json.loads(await update_task_status(task["id"], "concluido", t["version"]))
    assert c["status"] == "concluido"
    assert c["kanban"]["next_column"] is None
