"""Testes das tools MCP de LEITURA do quadro de specs.

O desenho anterior assumia que o agente que cria o trabalho e o que o executa. As
tools cobertas aqui existem para o caso oposto — o handoff — e o cenario central
destes testes e sempre o mesmo: chegar ao conteudo **sem** ter participado da
criacao e **sem** copiar id da UI web.

Mesmo padrao de ``test_mcp_specs_tasks.py``: SQLite em memoria, sem Qdrant/Ollama.
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
    delete_task,
    get_task,
    list_spec_comments,
    list_spec_workspaces,
    list_tasks,
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
    mcp_server.user_id_var.set("DESKTOP-01")
    mcp_server.client_name_var.set("cursor")
    yield


CORPO = (
    "## Requisitos\n- req 1\n## Subtarefas\n- [ ] passo 1\n"
    "## Criterios de aceite\n- teste passa"
)


async def _ws(project="mem0-shared", slug="ws-1", name="WS 1"):
    return json.loads(await create_spec_workspace(project, slug, name))


class TestGetTask:
    @pytest.mark.asyncio
    async def test_devolve_corpo_completo_e_version(self):
        """O corpo enriquecido do card era gravavel e movivel, mas nao legivel."""
        ws = await _ws()
        created = json.loads(await create_task(ws["id"], "Card A", CORPO))

        got = json.loads(await get_task(created["id"]))

        assert got["description"] == CORPO
        assert got["title"] == "Card A"
        # version e o que update_task_status exige como expected_version.
        assert got["version"] == created["version"]

    @pytest.mark.asyncio
    async def test_traz_orientacao_de_kanban(self):
        ws = await _ws()
        created = json.loads(await create_task(ws["id"], "Card A"))
        got = json.loads(await get_task(created["id"]))
        assert got["kanban"]["column"] == "tasks"

    @pytest.mark.asyncio
    async def test_id_inexistente_devolve_erro_e_nao_excecao(self):
        out = await get_task(str(uuid.uuid4()))
        assert out.startswith("Error:")


class TestListTasks:
    @pytest.mark.asyncio
    async def test_caminho_do_workspace_ate_um_task_id_assumivel(self):
        """O cenario que estava quebrado: descobrir o que puxar sem criar o card."""
        ws = await _ws()
        await create_task(ws["id"], "Card A")
        await create_task(ws["id"], "Card B")

        listed = json.loads(await list_tasks(ws["id"]))["results"]
        assert {t["title"] for t in listed} == {"Card A", "Card B"}

        # O id descoberto tem que servir para claim_task, que e o ponto do exercicio.
        claimed = json.loads(await claim_task(listed[0]["id"]))
        assert claimed["claimed"] is True

    @pytest.mark.asyncio
    async def test_version_vem_na_listagem(self):
        """Sem version aqui, todo avanco de coluna custaria uma leitura extra."""
        ws = await _ws()
        created = json.loads(await create_task(ws["id"], "Card A"))
        listed = json.loads(await list_tasks(ws["id"]))["results"]

        assert listed[0]["version"] == created["version"]

        # Prova de que o version listado basta para mover o card.
        moved = json.loads(await claim_task(listed[0]["id"]))
        out = json.loads(
            await update_task_status(
                listed[0]["id"], "revisao_codigo", moved["version"]
            )
        )
        assert out["updated"] is True

    @pytest.mark.asyncio
    async def test_descricao_omitida_por_padrao(self):
        """Listar um workspace inteiro com todos os corpos estoura o contexto."""
        ws = await _ws()
        await create_task(ws["id"], "Card A", CORPO)

        sem = json.loads(await list_tasks(ws["id"]))["results"][0]
        com = json.loads(await list_tasks(ws["id"], include_description=True))[
            "results"
        ][0]

        assert "description" not in sem
        assert com["description"] == CORPO

    @pytest.mark.asyncio
    async def test_filtra_por_coluna(self):
        ws = await _ws()
        a = json.loads(await create_task(ws["id"], "Card A"))
        await create_task(ws["id"], "Card B")
        await claim_task(a["id"])

        backlog = json.loads(await list_tasks(ws["id"], status="tasks"))["results"]
        andamento = json.loads(await list_tasks(ws["id"], status="em_andamento"))[
            "results"
        ]

        assert [t["title"] for t in backlog] == ["Card B"]
        assert [t["title"] for t in andamento] == ["Card A"]

    @pytest.mark.asyncio
    async def test_status_invalido_lista_os_validos(self):
        ws = await _ws()
        out = json.loads(await list_tasks(ws["id"], status="inventado"))
        assert "error" in out
        assert "tasks" in out["valid"]

    @pytest.mark.asyncio
    async def test_workspace_sem_cards_devolve_lista_vazia(self):
        """Vazio e resposta legitima, nao erro."""
        ws = await _ws()
        assert json.loads(await list_tasks(ws["id"]))["results"] == []


class TestListSpecComments:
    @pytest.mark.asyncio
    async def test_le_de_volta_o_que_foi_gravado(self):
        """Notas de revisao e evidencia de teste eram gravadas e nunca recuperadas."""
        ws = await _ws()
        task = json.loads(await create_task(ws["id"], "Card A"))

        await add_spec_comment("task", task["id"], "primeira nota")
        await add_spec_comment("task", task["id"], "evidencia de teste")

        out = json.loads(await list_spec_comments("task", task["id"]))["results"]

        assert [c["body"] for c in out] == ["primeira nota", "evidencia de teste"]
        assert out[0]["author"] == "DESKTOP-01"

    @pytest.mark.asyncio
    async def test_alvo_sem_comentarios_devolve_vazio(self):
        ws = await _ws()
        task = json.loads(await create_task(ws["id"], "Card A"))
        assert json.loads(await list_spec_comments("task", task["id"]))["results"] == []

    @pytest.mark.asyncio
    async def test_target_type_invalido_lista_os_validos(self):
        out = json.loads(await list_spec_comments("cartao", str(uuid.uuid4())))
        assert "error" in out
        assert set(out["valid"]) == {"workspace", "document", "task"}


class TestDeleteTask:
    @pytest.mark.asyncio
    async def test_remove_card_e_seus_comentarios(self):
        """Sem isto, um card de teste fica no quadro para sempre."""
        ws = await _ws()
        task = json.loads(await create_task(ws["id"], "Engano"))
        await add_spec_comment("task", task["id"], "nota")

        out = json.loads(await delete_task(task["id"]))
        assert out["deleted"] is True

        assert json.loads(await list_tasks(ws["id"]))["results"] == []
        assert (await get_task(task["id"])).startswith("Error:")

    @pytest.mark.asyncio
    async def test_id_inexistente_devolve_erro(self):
        assert (await delete_task(str(uuid.uuid4()))).startswith("Error:")


class TestDescobertaEntreProjetos:
    @pytest.mark.asyncio
    async def test_acha_por_slug_em_qualquer_projeto(self):
        """O caso que falhava: agente noutro repositorio da mesma feature.

        project_id segue o diretorio de trabalho, entao quem esta no repo vizinho
        recebia [] e concluia que nao havia spec - ou pior, criava um segundo
        workspace e fragmentava a spec.
        """
        await _ws(project="sysmovs", slug="minha-feature", name="Minha Feature")

        # Agente rodando em outro repositorio, que nao sabe o project_id.
        achados = json.loads(await list_spec_workspaces(slug="minha-feature"))

        assert [w["project_id"] for w in achados] == ["sysmovs"]

    @pytest.mark.asyncio
    async def test_sem_project_id_lista_todos(self):
        await _ws(project="sysmovs", slug="a", name="A")
        await _ws(project="db-sysmo-s1", slug="b", name="B")

        todos = json.loads(await list_spec_workspaces())

        assert {w["project_id"] for w in todos} == {"sysmovs", "db-sysmo-s1"}

    @pytest.mark.asyncio
    async def test_project_id_continua_escopando(self):
        """Comportamento anterior preservado para quem passa project_id."""
        await _ws(project="sysmovs", slug="a", name="A")
        await _ws(project="db-sysmo-s1", slug="b", name="B")

        so_um = json.loads(await list_spec_workspaces("sysmovs"))

        assert [w["project_id"] for w in so_um] == ["sysmovs"]

    @pytest.mark.asyncio
    async def test_slug_inexistente_devolve_vazio(self):
        await _ws(project="sysmovs", slug="a", name="A")
        assert json.loads(await list_spec_workspaces(slug="nao-existe")) == []
