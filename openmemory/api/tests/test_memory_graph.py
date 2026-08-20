"""Tests for openmemory/api/app/utils/memory_graph.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.utils.memory_graph import (
    GraphBuildParams,
    build_memory_graph,
    get_cached_or_build,
)


class DummyPoint:
    def __init__(self, point_id: str, data: str, project: str = "shared", vector: list | None = None):
        self.id = point_id
        self.payload = {
            "data": data,
            "project": project,
            "created_at": "2026-08-20T12:00:00Z",
            "updated_at": "2026-08-20T12:00:00Z",
        }
        self.vector = vector or [0.1, 0.2, 0.3]


class DummyHit:
    def __init__(self, point_id: str, score: float, data: str, project: str = "shared"):
        self.id = point_id
        self.score = score
        self.payload = {
            "data": data,
            "project": project,
            "created_at": "2026-08-20T12:00:00Z",
            "updated_at": "2026-08-20T12:00:00Z",
        }


def _make_mock_client(points: list[DummyPoint], hits_by_point_id: dict[str, list[DummyHit]]):
    client = MagicMock()
    vs = MagicMock()
    vs.collection_name = "openmemory"
    vs._create_filter.side_effect = lambda filters: filters
    vs.client.scroll.return_value = (points, None)

    def mock_search(query, vectors, top_k=8, filters=None):
        for p in points:
            if p.payload["data"] == query:
                return hits_by_point_id.get(p.id, [])[:top_k]
        return []

    vs.search.side_effect = mock_search
    client.vector_store = vs
    return client


def test_graph_build_params_normalization():
    params = GraphBuildParams(project="  my-project  ", top_k=0)
    normalized = params.normalized()
    assert normalized.project == "my-project"
    assert normalized.top_k == 1


def test_build_memory_graph_dedupe_and_orphan():
    points = [
        DummyPoint("1", "alpha"),
        DummyPoint("2", "beta"),
        DummyPoint("3", "gamma"),
    ]
    hits_by_id = {
        "1": [DummyHit("2", 0.9, "beta")],
        "2": [DummyHit("1", 0.9, "alpha")],
        "3": [],
    }
    mock_client = _make_mock_client(points, hits_by_id)

    with patch("app.utils.memory_graph.get_memory_client_safe", return_value=mock_client), patch(
        "app.utils.memory_graph.bind_active_collection"
    ) as mock_bind:
        payload = build_memory_graph(GraphBuildParams(top_k=8))

        mock_bind.assert_called_once_with(mock_client)
        assert len(payload["nodes"]) == 3
        assert len(payload["links"]) == 1
        assert payload["links"][0]["source"] == "1"
        assert payload["links"][0]["target"] == "2"

        nodes_by_id = {n["id"]: n for n in payload["nodes"]}
        assert nodes_by_id["1"]["orphan"] is False
        assert nodes_by_id["2"]["orphan"] is False
        assert nodes_by_id["3"]["orphan"] is True
        assert payload["meta"]["orphan_count"] == 1
        assert payload["meta"]["cached"] is False


def test_build_memory_graph_project_filter():
    points = [DummyPoint("1", "proj-a memory", project="proj-a")]
    mock_client = _make_mock_client(points, {"1": []})

    with patch("app.utils.memory_graph.get_memory_client_safe", return_value=mock_client):
        payload = build_memory_graph(GraphBuildParams(project="proj-a"))
        assert payload["nodes"][0]["project"] == "proj-a"
        assert mock_client.vector_store._create_filter.called


def test_build_memory_graph_top_k_respected():
    points = [DummyPoint("1", "alpha")]
    hits = [DummyHit(str(i), 0.9, f"item-{i}") for i in range(2, 20)]
    mock_client = _make_mock_client(points, {"1": hits})

    with patch("app.utils.memory_graph.get_memory_client_safe", return_value=mock_client):
        build_memory_graph(GraphBuildParams(top_k=3))
        mock_client.vector_store.search.assert_called_once()
        kwargs = mock_client.vector_store.search.call_args.kwargs
        assert kwargs["top_k"] == 3


def test_get_cached_or_build_and_refresh(monkeypatch):
    monkeypatch.setenv("MEM0_GRAPH_CACHE_TTL_SECONDS", "30")
    points = [DummyPoint("1", "alpha")]
    mock_client = _make_mock_client(points, {"1": []})

    with patch("app.utils.memory_graph.get_memory_client_safe", return_value=mock_client):
        params = GraphBuildParams(project="cached-test")
        first = get_cached_or_build(params, refresh=True)
        assert first["meta"]["cached"] is False

        second = get_cached_or_build(params)
        assert second["meta"]["cached"] is True

        refreshed = get_cached_or_build(params, refresh=True)
        assert refreshed["meta"]["cached"] is False


# --- task_06: paralelismo, logs estruturados e métricas -------------------


@pytest.fixture()
def _graph_logs():
    """Captura os eventos estruturados do builder, isolando o estado global de logging."""
    import logging

    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append
    graph_logger = logging.getLogger("app.utils.memory_graph")
    original_level = graph_logger.level
    original_disabled = graph_logger.disabled
    graph_logger.addHandler(handler)
    graph_logger.setLevel(logging.INFO)
    # O plugin de logging do pytest desabilita os loggers na fase de call e,
    # dependendo do hook, pode não reabilitá-los; garantimos aqui que o logger
    # do builder está habilitado durante o teste.
    graph_logger.disabled = False
    try:
        yield records
    finally:
        graph_logger.removeHandler(handler)
        graph_logger.setLevel(original_level)
        graph_logger.disabled = original_disabled


def _make_parallel_points(count: int = 24) -> list[DummyPoint]:
    points = [DummyPoint(str(i), f"memory-{i}") for i in range(count)]
    hits: dict[str, list[DummyHit]] = {}
    for i, point in enumerate(points):
        # Cada nó enxerga os 3 vizinhos subsequentes (determinístico).
        neighbors = [
            DummyHit(str(j), 0.9 - 0.1 * k, f"memory-{j}")
            for k, j in enumerate(((i + 1) % count, (i + 2) % count, (i + 3) % count))
        ]
        hits[str(i)] = neighbors
    return points, hits


def test_parallel_build_matches_serial_graph(monkeypatch):
    """Mesmo input → mesmo grafo, com 1 ou 8 buscas kNN em paralelo (6.1)."""
    points, hits = _make_parallel_points()
    mock_client = _make_mock_client(points, hits)
    params = GraphBuildParams(project="parallel-same-graph")

    with patch(
        "app.utils.memory_graph.get_memory_client_safe", return_value=mock_client
    ), patch("app.utils.memory_graph.bind_active_collection"):
        monkeypatch.setenv("MEM0_GRAPH_SEARCH_CONCURRENCY", "1")
        serial = build_memory_graph(params)

        # Limpa a contagem de chamadas para validar o cold-path paralelo.
        mock_client.vector_store.search.reset_mock()
        monkeypatch.setenv("MEM0_GRAPH_SEARCH_CONCURRENCY", "8")
        parallel = build_memory_graph(params)

    # Paralelismo realmente executou as N buscas (uma por nó).
    assert mock_client.vector_store.search.call_count == len(points)
    # Nós idênticos (o scroll é determinístico).
    assert parallel["nodes"] == serial["nodes"]
    # Conjunto de arestas idêntico: mesma identidade (source, target, score)
    # e mesmo peso (tolerância de 1e-6: o fator de recency usa datetime.now()
    # em sub-milissegundos, então o último dígito do weight pode variar entre
    # execuções — o recorte de arestas não muda).
    assert parallel["meta"]["node_count"] == serial["meta"]["node_count"]
    assert parallel["meta"]["link_count"] == serial["meta"]["link_count"]
    assert parallel["meta"]["orphan_count"] == serial["meta"]["orphan_count"]
    assert parallel["meta"]["link_count"] > 0

    def edge_signature(links):
        return [
            (link["source"], link["target"], round(link["score"], 9))
            for link in links
        ]

    assert edge_signature(parallel["links"]) == edge_signature(serial["links"])
    for a, b in zip(parallel["links"], serial["links"]):
        assert abs(a["weight"] - b["weight"]) < 1e-6
        assert a["score"] == b["score"]


def test_build_emits_structured_log_with_required_fields(monkeypatch, _graph_logs):
    """Cada GET do grafo loga os 6 campos obrigatórios da TechSpec (6.3).

    O evento estruturado é emitido pela camada ``get_cached_or_build`` (um por
    resposta do endpoint), com ``graph_build_ms`` do build original incluso no
    hit de cache.
    """
    monkeypatch.setenv("MEM0_GRAPH_CACHE_TTL_SECONDS", "30")
    points = [DummyPoint("1", "alpha"), DummyPoint("2", "beta")]
    hits = {"1": [DummyHit("2", 0.9, "beta")], "2": [DummyHit("1", 0.9, "alpha")]}
    mock_client = _make_mock_client(points, hits)

    with (
        patch("app.utils.memory_graph.get_memory_client_safe", return_value=mock_client),
        patch("app.utils.memory_graph.bind_active_collection"),
    ):
        get_cached_or_build(GraphBuildParams(project="log-fields-proj"), refresh=True)
        get_cached_or_build(GraphBuildParams(project="log-fields-proj"))

    events = [
        r.getMessage()
        for r in _graph_logs
        if "memory_graph graph_build_ms=" in r.getMessage()
    ]
    assert len(events) == 2  # um evento por GET (cold + warm)
    required = (
        "graph_build_ms=",
        "node_count=2",
        "link_count=1",
        "orphan_count=0",
        "project=log-fields-proj",
    )
    for message in events:
        for field in required:
            assert field in message, f"campo obrigatório ausente: {field} em {message!r}"
    assert "cache_hit=false" in events[0]
    assert "cache_hit=true" in events[1]
    # graph_build_ms do hit reaproveita o custo do build original (> 0).
    warm_ms = float(events[1].split("graph_build_ms=")[1].split()[0])
    assert warm_ms > 0


def test_get_cached_or_build_logs_cache_hit_true_on_second_call(monkeypatch, _graph_logs):
    """Smoke de cache_hit: segundo GET loga cache_hit=true (6.4)."""
    monkeypatch.setenv("MEM0_GRAPH_CACHE_TTL_SECONDS", "30")
    points = [DummyPoint("1", "alpha")]
    mock_client = _make_mock_client(points, {"1": []})
    params = GraphBuildParams(project="cache-hit-log")

    with (
        patch(
            "app.utils.memory_graph.get_memory_client_safe", return_value=mock_client
        ),
        patch("app.utils.memory_graph.bind_active_collection"),
    ):
        get_cached_or_build(params, refresh=True)
        get_cached_or_build(params)

    events = [
        r.getMessage()
        for r in _graph_logs
        if "memory_graph graph_build_ms=" in r.getMessage()
    ]
    assert any("cache_hit=false" in e for e in events)
    assert any("cache_hit=true" in e for e in events)


def test_graph_cache_and_build_metrics_recorded():
    """Métricas Prometheus de cache e latência do build são gravadas (6.3)."""
    from prometheus_client import REGISTRY

    def sample(name, project):
        # Counters expõem o sufixo duplo (ex.: ..._total_total); o histograma
        # expõe ..._count/..._sum. Aceita ambos os nomes.
        for family in REGISTRY.collect():
            for s in family.samples:
                if (
                    s.name in (name, name + "_total")
                    and s.labels.get("project") == project
                ):
                    return s.value
        return 0.0

    points = [DummyPoint("1", "alpha")]
    mock_client = _make_mock_client(points, {"1": []})
    params = GraphBuildParams(project="metrics-proj")

    hits_before = sample("memory_graph_cache_hit_total", "metrics-proj")
    misses_before = sample("memory_graph_cache_miss_total", "metrics-proj")
    build_count_before = sample("memory_graph_build_seconds_count", "metrics-proj")

    with patch(
        "app.utils.memory_graph.get_memory_client_safe", return_value=mock_client
    ), patch("app.utils.memory_graph.bind_active_collection"):
        get_cached_or_build(params, refresh=True)
        get_cached_or_build(params)

    assert sample("memory_graph_cache_miss_total", "metrics-proj") == misses_before + 1
    assert sample("memory_graph_cache_hit_total", "metrics-proj") == hits_before + 1
    assert sample("memory_graph_build_seconds_count", "metrics-proj") == build_count_before + 1


def test_slim_search_result_payload(monkeypatch):
    """Enxugamento do payload (6.2): hits não carregam data/owner."""
    points = [DummyPoint("1", "alpha"), DummyPoint("2", "beta")]
    mock_client = _make_mock_client(points, {"1": [DummyHit("2", 0.9, "beta")], "2": []})

    captured = []

    def spy_rank(results, **kwargs):
        captured.extend(results)
        from app.utils.recency import rank_search_results

        return rank_search_results(results, **kwargs)

    with (
        patch("app.utils.memory_graph.get_memory_client_safe", return_value=mock_client),
        patch("app.utils.memory_graph.bind_active_collection"),
        patch("app.utils.memory_graph.rank_search_results", side_effect=spy_rank),
    ):
        build_memory_graph(GraphBuildParams(project="slim-payload"))

    assert captured, "rank_search_results não recebeu resultados"
    for result in captured:
        assert set(result.keys()) == {
            "id",
            "created_at",
            "updated_at",
            "project",
            "score",
            "effective_score",
            "ranking_factors",
        }
        assert "memory" not in result
        assert "owner" not in result
