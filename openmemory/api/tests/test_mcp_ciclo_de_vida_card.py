"""Testes do ciclo de vida do TaskCard.

As lacunas cobertas aqui nao apareceriam num teste de caminho feliz: surgiram numa
execucao real que atravessou varios dias e em que uma verificacao de teste
reprovou. Cada classe corresponde a um criterio de aceite:

1. card reprovado volta a em_andamento pelo proprio assignee, sem passar pelo
   backlog e sem perder a atribuicao;
2. o prazo do claim e observavel e renovavel sem passar pelo backlog;
3. titulo e corpo podem ser corrigidos quando a decisao muda depois da criacao;
4. a expiracao automatica e distinguivel de um release manual.

SQLite em memoria, sem Qdrant/Ollama.
"""

import json
import os
import uuid
from datetime import timedelta

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_server
from app.database import Base
from app.mcp_server import (
    claim_task,
    create_spec_workspace,
    create_task,
    get_task,
    list_task_history,
    list_tasks,
    release_task,
    update_task,
    update_task_status,
)
from app.models import TaskCard, get_current_utc_time
from app.utils import claim_lease
from app.workers.spec_task_timeout_worker import SpecTaskTimeoutWorker


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
    mcp_server.user_id_var.set("S0258")
    mcp_server.client_name_var.set("cursor")
    yield


async def _card(title="Card"):
    ws = json.loads(await create_spec_workspace("dashboard-s1", "ws-1", "WS"))
    task = json.loads(await create_task(ws["id"], title, "corpo original"))
    return ws, task


async def _ate(task_id, coluna):
    """Leva o card ate `coluna` seguindo o pipeline, devolvendo a versao vigente."""
    out = json.loads(await claim_task(task_id))
    v = out["version"]
    for alvo in ("revisao_codigo", "fase_teste", "concluido"):
        out = json.loads(await update_task_status(task_id, alvo, v))
        v = out["version"]
        if alvo == coluna:
            break
    return v


class TestReprovadoVoltaParaCorrecao:
    @pytest.mark.asyncio
    async def test_assignee_reassume_card_em_fase_teste(self):
        """O cenario que quebrava: verificacao reprovou, precisa voltar a corrigir.

        Antes, claim_task exigia status == tasks, entao o proprio assignee recebia
        claimed=false apontando ELE MESMO como "outro responsavel".
        """
        _, task = await _card()
        await _ate(task["id"], "fase_teste")

        out = json.loads(await claim_task(task["id"]))

        assert out["claimed"] is True
        assert out["status"] == "em_andamento"
        assert out["assignee"] == "S0258"

    @pytest.mark.asyncio
    async def test_nao_passa_pelo_backlog_nem_perde_atribuicao(self):
        _, task = await _card()
        await _ate(task["id"], "fase_teste")

        await claim_task(task["id"])
        card = json.loads(await get_task(task["id"]))

        assert card["status"] == "em_andamento"
        assert card["assignee"] == "S0258"

        # O historico nao pode registrar passagem pelo backlog.
        hist = json.loads(await list_task_history(task["id"]))["results"]
        assert all(h["new_status"] != "tasks" for h in hist)

    @pytest.mark.asyncio
    async def test_reassume_tambem_de_revisao_codigo(self):
        _, task = await _card()
        await _ate(task["id"], "revisao_codigo")
        out = json.loads(await claim_task(task["id"]))
        assert out["claimed"] is True

    @pytest.mark.asyncio
    async def test_exclusividade_para_terceiros_continua_valendo(self, factory):
        """A mudanca vale so quando current_assignee == chamador."""
        _, task = await _card()
        await _ate(task["id"], "fase_teste")

        mcp_server.user_id_var.set("OUTRA-MAQUINA")
        out = json.loads(await claim_task(task["id"]))

        assert out["claimed"] is False
        assert out["current_assignee"] == "S0258"

    @pytest.mark.asyncio
    async def test_reassuncao_registra_versao_nova(self):
        _, task = await _card()
        v = await _ate(task["id"], "fase_teste")
        out = json.loads(await claim_task(task["id"]))
        assert out["version"] > v


class TestLeaseObservavel:
    @pytest.mark.asyncio
    async def test_claim_informa_o_prazo(self):
        """Antes nao havia como saber que o claim tinha prazo."""
        _, task = await _card()
        out = json.loads(await claim_task(task["id"]))
        assert out["claim_expires_at"]

    @pytest.mark.asyncio
    async def test_prazo_aparece_na_leitura_do_card(self):
        _, task = await _card()
        await claim_task(task["id"])

        card = json.loads(await get_task(task["id"]))
        listado = json.loads(await list_tasks(task["workspace_id"]))["results"][0]

        assert card["claim_expires_at"]
        assert listado["claim_expires_at"] == card["claim_expires_at"]

    @pytest.mark.asyncio
    async def test_card_no_backlog_nao_tem_prazo(self):
        """Sem lease correndo, o campo e None — ausencia e informacao."""
        _, task = await _card()
        card = json.loads(await get_task(task["id"]))
        assert card["claim_expires_at"] is None

    @pytest.mark.asyncio
    async def test_reassumir_renova_o_prazo(self):
        _, task = await _card()
        antes = json.loads(await claim_task(task["id"]))["claim_expires_at"]

        # Recua a atividade para simular tempo passando.
        db = mcp_server.SessionLocal()
        try:
            card = db.get(TaskCard, uuid.UUID(task["id"]))
            card.last_activity_at = get_current_utc_time() - timedelta(hours=10)
            db.commit()
        finally:
            db.close()

        depois = json.loads(await claim_task(task["id"]))["claim_expires_at"]
        assert depois > antes

    def test_prazo_acompanha_a_env_do_worker(self, monkeypatch):
        """O prazo informado ao cliente tem que ser o mesmo que o worker aplica."""
        monkeypatch.setenv("SPEC_TASK_TIMEOUT_HOURS", "2")
        base = get_current_utc_time()
        assert claim_lease.claim_expires_at(base) == base + timedelta(hours=2)
        assert claim_lease.claim_timeout_hours() == 2.0

    def test_expiracao_desligada_nao_inventa_prazo(self, monkeypatch):
        monkeypatch.setenv("SPEC_TASK_TIMEOUT_HOURS", "0")
        assert claim_lease.claim_expires_at(get_current_utc_time()) is None

    def test_env_invalida_cai_no_padrao(self, monkeypatch):
        monkeypatch.setenv("SPEC_TASK_TIMEOUT_HOURS", "abc")
        assert claim_lease.claim_timeout_hours() == claim_lease.DEFAULT_TIMEOUT_HOURS


class TestExpiracaoDistinguivel:
    @pytest.mark.asyncio
    async def test_historico_marca_liberacao_por_timeout(self, factory):
        """Antes, um card que voltou sozinho era igual a um devolvido de proposito."""
        _, task = await _card()
        await claim_task(task["id"])

        db = factory()
        try:
            card = db.get(TaskCard, uuid.UUID(task["id"]))
            card.last_activity_at = get_current_utc_time() - timedelta(hours=48)
            db.commit()
            SpecTaskTimeoutWorker(
                timeout_hours=24.0, session_factory=factory
            ).process_once()
        finally:
            db.close()

        hist = json.loads(await list_task_history(task["id"]))["results"]
        expiracao = [h for h in hist if h["new_status"] == "tasks"]

        assert len(expiracao) == 1
        assert expiracao[0]["by_timeout"] is True
        assert expiracao[0]["changed_by"] == "system:timeout"

    @pytest.mark.asyncio
    async def test_release_manual_nao_e_marcado_como_timeout(self):
        _, task = await _card()
        await claim_task(task["id"])
        await release_task(task["id"])

        hist = json.loads(await list_task_history(task["id"]))["results"]
        volta = [h for h in hist if h["new_status"] == "tasks"]

        assert len(volta) == 1
        assert volta[0]["by_timeout"] is False
        assert volta[0]["changed_by"] == "S0258"

    @pytest.mark.asyncio
    async def test_card_sem_movimentacao_tem_historico_vazio(self):
        _, task = await _card()
        assert json.loads(await list_task_history(task["id"]))["results"] == []


class TestEdicaoDeCard:
    @pytest.mark.asyncio
    async def test_corrige_titulo_e_corpo(self):
        """Caso real: dois ADRs invertidos por medicao depois dos cards criados."""
        _, task = await _card("Tarefa 06: repositorio com as tres consultas")

        out = json.loads(
            await update_task(
                task["id"],
                task["version"],
                title="Tarefa 06: repositorio com consulta consolidada",
                description="corpo revisado",
            )
        )

        assert out["updated"] is True
        card = json.loads(await get_task(task["id"]))
        assert card["title"] == "Tarefa 06: repositorio com consulta consolidada"
        assert card["description"] == "corpo revisado"

    @pytest.mark.asyncio
    async def test_campo_omitido_nao_e_apagado(self):
        _, task = await _card("Titulo")
        await update_task(task["id"], task["version"], title="Outro")

        card = json.loads(await get_task(task["id"]))
        assert card["title"] == "Outro"
        assert card["description"] == "corpo original"

    @pytest.mark.asyncio
    async def test_conflito_de_versao_nao_sobrescreve(self):
        _, task = await _card("Titulo")
        await update_task(task["id"], task["version"], title="Primeira")

        out = json.loads(
            await update_task(task["id"], task["version"], title="Atrasada")
        )

        assert out["conflict"] is True
        assert out["current_title"] == "Primeira"
        card = json.loads(await get_task(task["id"]))
        assert card["title"] == "Primeira"

    @pytest.mark.asyncio
    async def test_sem_campos_avisa_em_vez_de_bumpar_versao(self):
        _, task = await _card()
        out = json.loads(await update_task(task["id"], task["version"]))

        assert "error" in out
        card = json.loads(await get_task(task["id"]))
        assert card["version"] == task["version"]

    @pytest.mark.asyncio
    async def test_edicao_renova_o_lease(self):
        _, task = await _card()
        claimed = json.loads(await claim_task(task["id"]))

        db = mcp_server.SessionLocal()
        try:
            card = db.get(TaskCard, uuid.UUID(task["id"]))
            card.last_activity_at = get_current_utc_time() - timedelta(hours=10)
            db.commit()
        finally:
            db.close()

        await update_task(task["id"], claimed["version"], title="Editado")
        depois = json.loads(await get_task(task["id"]))["claim_expires_at"]

        assert depois > claimed["claim_expires_at"]

    @pytest.mark.asyncio
    async def test_id_inexistente_devolve_erro(self):
        out = await update_task(str(uuid.uuid4()), 1, title="x")
        assert out.startswith("Error:")
