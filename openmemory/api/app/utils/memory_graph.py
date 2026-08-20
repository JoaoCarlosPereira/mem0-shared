"""Build and cache the similarity graph exposed by the memories API."""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.utils.memory import get_memory_client_safe
from app.utils.metrics import (
    GRAPH_BUILD_DURATION,
    GRAPH_CACHE_HITS,
    GRAPH_CACHE_MISSES,
)
from app.utils.partitioning import bind_active_collection
from app.utils.recency import rank_search_results

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_TOP_K = 8
DEFAULT_GRAPH_CACHE_TTL_SECONDS = 30.0
DEFAULT_GRAPH_EDGE_MIN_EFFECTIVE_SCORE = 0.0
# task_06: concorrência limitada do cold-path (buscas kNN em paralelo).
DEFAULT_GRAPH_SEARCH_CONCURRENCY = 8


def _search_concurrency() -> int:
    return max(
        1,
        int(
            os.getenv(
                "MEM0_GRAPH_SEARCH_CONCURRENCY",
                str(DEFAULT_GRAPH_SEARCH_CONCURRENCY),
            )
        ),
    )


def _project_label(project: str | None) -> str:
    """Rótulo de métrica/log para o escopo do grafo (project ou 'global')."""
    return project or "global"


@dataclass(frozen=True)
class GraphBuildParams:
    """Parameters that determine one graph snapshot."""

    project: str | None = None
    top_k: int = DEFAULT_GRAPH_TOP_K
    edge_min_effective_score: float | None = None

    def normalized(self) -> "GraphBuildParams":
        return GraphBuildParams(
            project=self.project.strip() if self.project and self.project.strip() else None,
            top_k=max(1, int(self.top_k)),
            edge_min_effective_score=self.edge_min_effective_score,
        )


def _edge_threshold(params: GraphBuildParams) -> float:
    if params.edge_min_effective_score is not None:
        return float(params.edge_min_effective_score)
    return float(
        os.getenv(
            "MEM0_GRAPH_EDGE_MIN_EFFECTIVE_SCORE",
            str(DEFAULT_GRAPH_EDGE_MIN_EFFECTIVE_SCORE),
        )
    )


def _cache_ttl_seconds() -> float:
    return max(
        0.0,
        float(
            os.getenv(
                "MEM0_GRAPH_CACHE_TTL_SECONDS",
                str(DEFAULT_GRAPH_CACHE_TTL_SECONDS),
            )
        ),
    )


def _payload(point: Any) -> dict[str, Any]:
    payload = getattr(point, "payload", None)
    return payload if isinstance(payload, dict) else {}


def _point_id(point: Any) -> str:
    return str(getattr(point, "id", "") or "")


def _point_vector(point: Any) -> Any:
    vector = getattr(point, "vector", None)
    if isinstance(vector, dict):
        return vector.get("default") or next(iter(vector.values()), None)
    return vector


def _scroll_points(vector_store, project: str | None) -> list[Any]:
    """Scroll every point in the active collection without a node ceiling."""
    filters = {"project": project} if project else {}
    scroll_filter = vector_store._create_filter(filters) if filters else None
    points: list[Any] = []
    offset = None
    while True:
        records, offset = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            scroll_filter=scroll_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        points.extend(records or [])
        if offset is None:
            break
    return points


def _node(point: Any) -> dict[str, Any]:
    payload = _payload(point)
    content = str(payload.get("data") or "")
    return {
        "id": _point_id(point),
        "name": content[:160],
        "project": payload.get("project"),
        "orphan": True,
        "created_at": payload.get("created_at"),
    }


def _search_result(hit: Any) -> dict[str, Any]:
    """Payload enxuto do hit (task_06).

    Mantém apenas os campos consumidos pelo ranking/limiar. O conteúdo
    completo da memória (``data``) e o ``owner`` nunca eram usados pelo
    builder e inflavam a memória alocada (N nós × top_k hits). ``created_at``
    permanece como fallback do ``recency_factor`` quando ``updated_at``
    está ausente.
    """
    payload = _payload(hit)
    return {
        "id": _point_id(hit),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "project": payload.get("project"),
        "score": getattr(hit, "score", 0.0),
    }


def _edges_for_point(
    point: Any,
    vector_store,
    params: GraphBuildParams,
    node_ids: set[str],
    threshold: float,
) -> list[dict[str, Any]]:
    """Busca kNN + ranking + corte de limiar para um único nó.

    Puro em relação ao ponto (sem estado compartilhado entre iterações),
    de modo que pode rodar em paralelo sem alterar o resultado.
    """
    source = _point_id(point)
    vector = _point_vector(point)
    if not source or source not in node_ids or vector is None:
        return []
    filters = {"project": params.project} if params.project else None
    hits = vector_store.search(
        query=str(_payload(point).get("data") or ""),
        vectors=vector,
        top_k=params.top_k,
        filters=filters,
    )
    results = [_search_result(hit) for hit in hits or [] if _point_id(hit) in node_ids]
    rank_search_results(
        results,
        preferred_project=params.project,
        annotate=True,
    )
    candidates: list[dict[str, Any]] = []
    for result in results:
        target = result["id"]
        effective_score = result.get("effective_score")
        if target == source or not isinstance(effective_score, (int, float)):
            continue
        if effective_score < threshold:
            continue
        key = tuple(sorted((source, target)))
        candidates.append(
            {
                "source": key[0],
                "target": key[1],
                "weight": effective_score,
                "score": result.get("score", 0.0),
            }
        )
    return candidates


def _log_graph_event(payload: dict[str, Any], params: GraphBuildParams, *, cache_hit: bool) -> None:
    """Log estruturado exigido pela TechSpec (Monitoramento e Observabilidade).

    Campos obrigatórios: ``graph_build_ms``, ``node_count``, ``link_count``,
    ``orphan_count``, ``cache_hit``, ``project``.
    """
    meta = payload["meta"]
    logger.info(
        "memory_graph graph_build_ms=%.2f node_count=%d link_count=%d "
        "orphan_count=%d cache_hit=%s project=%s",
        meta.get("graph_build_ms") or 0.0,
        meta["node_count"],
        meta["link_count"],
        meta["orphan_count"],
        str(cache_hit).lower(),
        params.project,
    )


def build_memory_graph(params: GraphBuildParams | None = None) -> dict[str, Any]:
    """Materialize the complete memory similarity graph.

    Cold path (task_06): as N buscas kNN rodam em paralelo com
    concorrência limitada (env ``MEM0_GRAPH_SEARCH_CONCURRENCY``, padrão 8).
    A agregação das arestas preserva a ordem de scroll dos pontos, então o
    mesmo input produz exatamente o mesmo grafo em qualquer execução
    (paralela ou serial).
    """
    started = time.monotonic()
    params = (params or GraphBuildParams()).normalized()
    client = get_memory_client_safe()
    if client is None:
        raise RuntimeError("Memory client is currently unavailable")

    bind_active_collection(client)
    vector_store = client.vector_store
    points = _scroll_points(vector_store, params.project)
    nodes = [_node(point) for point in points if _point_id(point)]
    node_ids = {node["id"] for node in nodes}
    threshold = _edge_threshold(params)

    # Paralelismo limitado: o I/O domina (Qdrant), então threads bastam;
    # ``pool.map`` preserva a ordem de scroll dos pontos.
    workers = _search_concurrency()
    if len(points) > 1 and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            candidate_lists = list(
                pool.map(
                    lambda p: _edges_for_point(p, vector_store, params, node_ids, threshold),
                    points,
                )
            )
    else:
        candidate_lists = [
            _edges_for_point(p, vector_store, params, node_ids, threshold) for p in points
        ]

    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for candidates in candidate_lists:
        for candidate in candidates:
            key = (candidate["source"], candidate["target"])
            current = edges.get(key)
            if current is None or candidate["weight"] > current["weight"]:
                edges[key] = candidate

    edge_list = list(edges.values())
    connected = {node_id for edge in edge_list for node_id in (edge["source"], edge["target"])}
    for node in nodes:
        node["orphan"] = node["id"] not in connected

    build_ms = (time.monotonic() - started) * 1000.0

    return {
        "nodes": nodes,
        "links": edge_list,
        "meta": {
            "node_count": len(nodes),
            "link_count": len(edge_list),
            "orphan_count": sum(node["orphan"] for node in nodes),
            "cached": False,
            # Interno (retirado do JSON pela response_model): custo do build,
            # reaproveitado no log estruturado do hit de cache.
            "graph_build_ms": build_ms,
        },
    }


_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _cache_key(params: GraphBuildParams) -> tuple[Any, ...]:
    return (
        params.project,
        params.top_k,
        _edge_threshold(params),
    )


def _mark_cached(payload: dict[str, Any], cached: bool) -> dict[str, Any]:
    return {
        **payload,
        "meta": {**payload["meta"], "cached": cached},
    }


def get_cached_or_build(
    params: GraphBuildParams | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return a fresh graph or a short-lived cached snapshot."""
    params = (params or GraphBuildParams()).normalized()
    label = _project_label(params.project)
    key = _cache_key(params)
    now = time.monotonic()
    if not refresh:
        with _cache_lock:
            cached = _cache.get(key)
            if cached and now - cached[0] <= _cache_ttl_seconds():
                GRAPH_CACHE_HITS.labels(project=label).inc()
                _log_graph_event(cached[1], params, cache_hit=True)
                return _mark_cached(cached[1], True)

    GRAPH_CACHE_MISSES.labels(project=label).inc()
    payload = build_memory_graph(params)
    _log_graph_event(payload, params, cache_hit=False)
    GRAPH_BUILD_DURATION.labels(project=label).observe(payload["meta"]["graph_build_ms"] / 1000.0)
    with _cache_lock:
        _cache[key] = (time.monotonic(), payload)
    return payload
