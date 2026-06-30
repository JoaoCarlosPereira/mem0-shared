"""Testes da exposição de `owner` e do boost por grupo na busca (task_04 / ADR-003).

Reusa o padrão de mock do memory client de ``test_mcp_read_project.py`` — roda sem
Qdrant/Ollama.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app import mcp_server
from app.mcp_server import search_memory
from app.utils import recency


def _hit(mem_id, data, project, score=0.9, **payload):
    base = {"data": data, "project": project, "hash": f"h-{mem_id}"}
    base.update(payload)
    return SimpleNamespace(id=mem_id, score=score, payload=base)


def _make_client(search_return=None):
    client = MagicMock()
    client.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    client.embedding_model.model = "test-embed-model"
    client.vector_store.search.return_value = search_return or []
    client.vector_store.list.return_value = []
    return client


@pytest.fixture
def patched_client():
    client = _make_client()
    with (
        patch.object(mcp_server, "get_memory_client_safe", return_value=client),
        patch.object(mcp_server, "bind_active_collection"),
        patch.object(mcp_server.read_cache, "get_search", return_value=None),
        patch.object(mcp_server.read_cache, "set_search"),
        patch.object(mcp_server.read_cache, "get_embedding", return_value=None),
        patch.object(mcp_server.read_cache, "set_embedding"),
    ):
        yield client


@pytest.mark.asyncio
async def test_search_result_includes_owner_from_payload(patched_client):
    client = patched_client
    client.vector_store.search.return_value = [
        _hit("1", "coffee", "A", hostname="host-x")
    ]
    mcp_server.user_id_var.set("host-req")
    mcp_server.client_name_var.set("cursor")

    with patch.object(mcp_server, "group_of_hostname", return_value=None):
        out = await search_memory("coffee", project="A")
    data = json.loads(out)
    assert data["results"][0]["owner"] == "host-x"


@pytest.mark.asyncio
async def test_missing_hostname_yields_owner_none(patched_client):
    client = patched_client
    client.vector_store.search.return_value = [_hit("1", "coffee", "A")]  # sem hostname
    mcp_server.user_id_var.set("host-req")
    mcp_server.client_name_var.set("cursor")

    with patch.object(mcp_server, "group_of_hostname", return_value=None):
        out = await search_memory("coffee", project="A")
    data = json.loads(out)
    assert data["results"][0]["owner"] is None


@pytest.mark.asyncio
async def test_same_group_result_is_boosted_in_output(patched_client):
    client = patched_client
    # "outro" tem score maior; "meu" é do mesmo grupo do solicitante.
    client.vector_store.search.return_value = [
        _hit("outro", "x", "A", score=0.80, hostname="host-b"),
        _hit("meu", "y", "A", score=0.50, hostname="host-a"),
    ]
    mcp_server.user_id_var.set("host-req")
    mcp_server.client_name_var.set("cursor")

    author_groups = {"host-a": "Equipe A", "host-b": "Equipe B"}
    with (
        # grupo do solicitante = Equipe A
        patch.object(mcp_server, "group_of_hostname", return_value="Equipe A"),
        # grupo do autor resolvido dentro do ranqueamento
        patch.object(recency, "group_of_hostname", side_effect=lambda h: author_groups.get(h)),
        patch.object(recency, "SEARCH_RECENCY_HALFLIFE_DAYS", 0.0),
    ):
        out = await search_memory("q", project="A")
    data = json.loads(out)
    ids = [r["id"] for r in data["results"]]
    assert ids[0] == "meu", "mesmo grupo (0.50*2.5) deve superar outro grupo (0.80)"
    assert set(ids) == {"meu", "outro"}, "memória de outro grupo permanece nos resultados"


@pytest.mark.asyncio
async def test_requester_group_resolved_from_user_id_var(patched_client):
    client = patched_client
    client.vector_store.search.return_value = [_hit("1", "c", "A", hostname="h")]
    mcp_server.user_id_var.set("host-solicitante")
    mcp_server.client_name_var.set("cursor")

    with patch.object(mcp_server, "group_of_hostname", return_value="G") as resolver:
        await search_memory("c", project="A")
    # O grupo do solicitante é resolvido a partir do hostname normalizado da conexão.
    resolver.assert_any_call("host-solicitante")
