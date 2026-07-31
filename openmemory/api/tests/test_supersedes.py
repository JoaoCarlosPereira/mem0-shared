"""Tests for supersedes / obsolete filtering and mark_obsolete."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from mem0.vector_stores.qdrant import Qdrant, _ACTIVE_STATE_FILTER, _AUDIT_STATE_FILTER

from app import mcp_server
from app.mcp_server import mark_obsolete, search_memory
from app.utils.supersedes import mark_points_obsolete
from app.utils.write_queue import WriteJob
from app.workers.write_worker import WriteWorker


def test_active_state_filter_excludes_obsolete():
    blob = str(_ACTIVE_STATE_FILTER)
    assert "obsolete" in blob
    assert "quarantined" in blob


def test_audit_state_filter_allows_obsolete():
    blob = str(_AUDIT_STATE_FILTER)
    assert "obsolete" in blob


def test_merge_governance_include_obsolete_switches_guard():
    vs = MagicMock()
    vs._merge_governance_filters = lambda filters, include_obsolete=False: (
        Qdrant._merge_governance_filters(vs, filters, include_obsolete=include_obsolete)
    )
    active = Qdrant._merge_governance_filters(vs, {"project": "A"}, include_obsolete=False)
    audit = Qdrant._merge_governance_filters(vs, {"project": "A"}, include_obsolete=True)
    assert active != audit
    assert "obsolete" in str(active)
    assert active["AND"][0] == {"project": "A"}


def test_mark_points_obsolete_sets_payload():
    client = MagicMock()
    client.vector_store.collection_name = "openmemory"
    client.vector_store.client.retrieve.return_value = [SimpleNamespace(id="m1")]
    with patch("app.utils.partitioning.bind_active_collection"):
        out = mark_points_obsolete(client, ["m1"], superseded_by="new-1")
    assert out["updated"] == ["m1"]
    assert out["missing"] == []
    kwargs = client.vector_store.client.set_payload.call_args.kwargs
    assert kwargs["payload"]["state"] == "obsolete"
    assert kwargs["payload"]["superseded_by"] == "new-1"
    assert kwargs["points"] == ["m1"]


def test_mark_points_obsolete_missing_id():
    client = MagicMock()
    client.vector_store.collection_name = "openmemory"
    client.vector_store.client.retrieve.return_value = []
    with patch("app.utils.partitioning.bind_active_collection"):
        out = mark_points_obsolete(client, ["missing"])
    assert out["updated"] == []
    assert out["missing"] == ["missing"]
    client.vector_store.client.set_payload.assert_not_called()


@pytest.mark.asyncio
async def test_mark_obsolete_mcp_tool():
    client = MagicMock()
    with (
        patch.object(mcp_server, "get_memory_client_safe", return_value=client),
        patch("app.utils.supersedes.mark_points_obsolete", return_value={"updated": ["a"], "missing": []}) as m,
    ):
        out = await mark_obsolete(["a"], superseded_by="b")
    data = __import__("json").loads(out)
    assert data["status"] == "ok"
    assert data["updated"] == ["a"]
    m.assert_called_once()


@pytest.mark.asyncio
async def test_search_passes_include_obsolete_to_vector_store():
    client = MagicMock()
    client.embedding_model.model = "m"
    client.embedding_model.embed.return_value = [0.1]
    client.vector_store.search.return_value = []
    with (
        patch.object(mcp_server, "get_memory_client_safe", return_value=client),
        patch.object(mcp_server, "bind_active_collection"),
        patch.object(mcp_server.read_cache, "get_search", return_value=None),
        patch.object(mcp_server.read_cache, "set_search"),
        patch.object(mcp_server.read_cache, "get_embedding", return_value=None),
        patch.object(mcp_server.read_cache, "set_embedding"),
    ):
        mcp_server.user_id_var.set("host")
        await search_memory("q", project="sysmovs", include_obsolete=True)
    assert client.vector_store.search.call_args.kwargs["include_obsolete"] is True


@pytest.mark.asyncio
async def test_worker_applies_supersedes_after_add():
    client = MagicMock()
    client.add.return_value = {
        "results": [{"id": "new-id", "event": "ADD", "memory": "fixed"}]
    }
    job = WriteJob(
        id="11111111-1111-1111-1111-111111111111",
        project="sysmovs",
        hostname="S0258",
        client_name="cursor",
        text="correction",
        created_at="",
        extras={"supersedes": ["725104c0-4cf8-4af3-b21a-2d979b0caca5"]},
    )
    queue = MagicMock()
    queue.dequeue.return_value = [job]
    # Preferência do worker pós-timeout: mark_done_if_processing. MagicMock
    # auto-expõe o atributo; configurar o retorno evita cair no early-return.
    queue.mark_done_if_processing.return_value = True
    worker = WriteWorker(
        queue=queue,
        client_provider=lambda: client,
        upsert_project=MagicMock(),
        max_concurrency=1,
    )
    with (
        patch.object(worker, "_maybe_dual_write"),
        patch.object(worker, "_catalog_project"),
        patch("app.workers.write_worker.bind_active_collection"),
        patch("app.workers.write_worker.read_cache") as rc,
        patch("app.utils.supersedes.mark_points_obsolete") as mark,
        patch("app.workers.write_worker.usage_attribution"),
    ):
        mark.return_value = {"updated": ["725104c0-4cf8-4af3-b21a-2d979b0caca5"], "missing": []}
        n = await worker.process_once()
    assert n == 1
    mark.assert_called_once()
    assert mark.call_args.args[1] == ["725104c0-4cf8-4af3-b21a-2d979b0caca5"]
    assert mark.call_args.kwargs["superseded_by"] == "new-id"
    # metadata must include state=active
    add_kwargs = client.add.call_args.kwargs
    assert add_kwargs["metadata"]["state"] == "active"
    assert add_kwargs["metadata"]["supersedes"] == [
        "725104c0-4cf8-4af3-b21a-2d979b0caca5"
    ]
    queue.mark_done_if_processing.assert_called_once_with(job.id)
    rc.invalidate_search.assert_called_once_with("sysmovs")
