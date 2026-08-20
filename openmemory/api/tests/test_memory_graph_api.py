"""API tests for the shared-memory graph endpoint."""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.memories import router as memories_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(memories_router)
    return TestClient(app)


def _payload() -> dict:
    return {
        "nodes": [
            {
                "id": "memory-1",
                "name": "first memory",
                "project": "alpha",
                "orphan": False,
                "created_at": "2026-08-20T12:00:00Z",
            },
            {
                "id": "memory-2",
                "name": "second memory",
                "project": "alpha",
                "orphan": True,
                "created_at": "2026-08-20T12:01:00Z",
            },
        ],
        "links": [
            {
                "source": "memory-1",
                "target": "memory-2",
                "weight": 0.81,
                "score": 0.79,
            }
        ],
        "meta": {
            "node_count": 2,
            "link_count": 1,
            "orphan_count": 1,
            "cached": False,
        },
    }


def test_graph_endpoint_returns_nodes_links_and_meta():
    client = _client()
    with (
        patch("app.routers.memories.get_cached_or_build", return_value=_payload()) as build,
        patch("app.utils.read_audit.record_memory_reads") as record,
    ):
        response = client.get("/api/v1/memories/graph")

    assert response.status_code == 200
    assert response.json() == _payload()
    build.assert_called_once()
    params = build.call_args.args[0]
    assert params.project is None
    assert params.top_k == 8
    assert build.call_args.kwargs == {"refresh": False}
    record.assert_called_once()
    assert record.call_args.kwargs["memory_ids"] == ["memory-1", "memory-2"]


def test_graph_endpoint_passes_project_top_k_and_refresh():
    client = _client()
    with (
        patch("app.routers.memories.get_cached_or_build", return_value=_payload()) as build,
        patch("app.utils.read_audit.record_memory_reads"),
    ):
        response = client.get(
            "/api/v1/memories/graph",
            params={"project": "alpha", "top_k": 4, "refresh": "true"},
        )

    assert response.status_code == 200
    params = build.call_args.args[0]
    assert params.project == "alpha"
    assert params.top_k == 4
    assert build.call_args.kwargs == {"refresh": True}


def test_graph_endpoint_returns_503_when_memory_client_is_unavailable():
    client = _client()
    with patch(
        "app.routers.memories.get_cached_or_build",
        side_effect=RuntimeError("Memory client is currently unavailable"),
    ):
        response = client.get("/api/v1/memories/graph")

    assert response.status_code == 503
    assert response.json()["detail"] == "Memory client is currently unavailable"


def test_graph_endpoint_returns_500_for_unexpected_builder_error():
    client = _client()
    with patch(
        "app.routers.memories.get_cached_or_build",
        side_effect=ValueError("bad graph"),
    ):
        response = client.get("/api/v1/memories/graph")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to build memory graph"


# --- task_06: cache_hit via endpoint + contrato estável --------------------


def test_graph_endpoint_second_get_hits_cache_and_contract():
    """Segundo GET sem refresh → cache_hit=true e contrato nodes/links/meta estável."""
    import app.utils.memory_graph as mg

    from tests.test_memory_graph import DummyHit, DummyPoint, _make_mock_client

    points = [
        DummyPoint("m-1", "alpha", project="alpha"),
        DummyPoint("m-2", "beta", project="alpha"),
        DummyPoint("m-3", "gamma", project="alpha"),
    ]
    hits = {
        "m-1": [DummyHit("m-2", 0.9, "beta", project="alpha")],
        "m-2": [DummyHit("m-1", 0.9, "alpha", project="alpha")],
        "m-3": [],
    }
    mock_client = _make_mock_client(points, hits)

    client = _client()
    saved_cache = dict(mg._cache)
    mg._cache.clear()
    try:
        with (
            patch(
                "app.utils.memory_graph.get_memory_client_safe",
                return_value=mock_client,
            ),
            patch("app.utils.memory_graph.bind_active_collection"),
            patch("app.utils.read_audit.record_memory_reads"),
        ):
            first = client.get("/api/v1/memories/graph")
            second = client.get("/api/v1/memories/graph")
    finally:
        mg._cache.clear()
        mg._cache.update(saved_cache)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["meta"]["cached"] is False
    assert second.json()["meta"]["cached"] is True

    # O build (N buscas kNN) só acontece no cold path.
    assert mock_client.vector_store.search.call_count == len(points)

    # Contrato JSON público inalterado (6.4): mesmas chaves, sem campos internos.
    body = second.json()
    assert set(body.keys()) == {"nodes", "links", "meta"}
    assert set(body["meta"].keys()) == {
        "node_count",
        "link_count",
        "orphan_count",
        "cached",
    }
    for node in body["nodes"]:
        assert set(node.keys()) == {"id", "name", "project", "orphan", "created_at"}
    for link in body["links"]:
        assert set(link.keys()) == {"source", "target", "weight", "score"}
    assert body["meta"]["node_count"] == len(body["nodes"])
    assert body["meta"]["link_count"] == len(body["links"])
    assert body["meta"]["orphan_count"] == sum(1 for n in body["nodes"] if n["orphan"])
    assert body["links"][0]["source"] == "m-1"
    assert body["links"][0]["target"] == "m-2"
