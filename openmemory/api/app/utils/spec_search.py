"""Indexação e busca semântica de specs concluídas (Tarefa 6 / ADR-006).

Specs concluídas são indexadas numa collection Qdrant **dedicada**
(``openmemory_specs``), isolada da collection de memórias (``openmemory``), mas
reaproveitando o **mesmo** client ``mem0.Memory`` (mesma conexão Qdrant e o mesmo
``embedding_model`` já configurado em ``app.utils.memory``) — apenas com um nome
de collection diferente. Assim não há duplicação de configuração de embedding.

A primitiva ``semantic_search(embedder, vector_store, ...)`` é parametrizada por
(embedder, vector_store) e é a única implementação de "embed + buscar no vetor +
mapear payload"; o ranqueamento reaproveita ``recency.rank_search_results`` (o
mesmo boost de grupo/projeto calibrado para memórias) — sem lógica de busca
duplicada entre memórias e specs (ADR-006).

Simplificação intencional de MVP: specs usam uma collection **fixa**
(``openmemory_specs``), sem o blue-green/``PartitionResolver`` da collection de
memórias. Se no futuro specs precisarem de migração blue-green, este utilitário é
o ponto de evolução natural.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional
from uuid import UUID

from app.models import SpecDocument, SpecWorkspace, SpecWorkspaceStatus, get_current_utc_time
from app.utils.datetime_format import format_utc_iso
from app.utils.groups import group_of_hostname
from app.utils.memory import get_memory_client_safe
from app.utils.recency import normalize_project_name, rank_search_results
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Collection Qdrant dedicada a specs (ADR-006) — nunca ``openmemory``.
SPECS_COLLECTION = "openmemory_specs"
DEFAULT_SPECS_TOP_K = 10

_specs_vector_store = None  # cache por processo do vector store de specs


def get_specs_vector_store(base_client=None):
    """Vector store Qdrant apontando para ``openmemory_specs``.

    Reaproveita a conexão (``QdrantClient``) e os parâmetros do vector store do
    client de memórias, trocando apenas a collection — sem nova configuração de
    conexão. Retorna ``None`` se o client de memórias está indisponível.
    """
    global _specs_vector_store
    if _specs_vector_store is not None:
        return _specs_vector_store

    base = base_client or get_memory_client_safe()
    if base is None:
        return None
    base_vs = getattr(base, "vector_store", None)
    if base_vs is None:
        return None

    from mem0.vector_stores.qdrant import Qdrant

    _specs_vector_store = Qdrant(
        collection_name=SPECS_COLLECTION,
        embedding_model_dims=getattr(base_vs, "embedding_model_dims", 768),
        client=getattr(base_vs, "client", None),
        on_disk=getattr(base_vs, "on_disk", False),
    )
    return _specs_vector_store


def reset_specs_vector_store():
    """Descarta o cache do vector store de specs (testes / troca de config)."""
    global _specs_vector_store
    _specs_vector_store = None


def _resolve_backends(embedder, vector_store):
    """Resolve (embedder, vector_store) a partir do client de memórias, se omitidos."""
    if embedder is not None and vector_store is not None:
        return embedder, vector_store
    client = get_memory_client_safe()
    if client is None:
        return None, None
    embedder = embedder or getattr(client, "embedding_model", None)
    vector_store = vector_store or get_specs_vector_store(client)
    return embedder, vector_store


# --------------------------------------------------------------------------- #
# Primitiva compartilhada de busca (parametrizada por embedder + vector store)
# --------------------------------------------------------------------------- #
def semantic_search(
    embedder,
    vector_store,
    query: str,
    *,
    top_k: int,
    payload_mapper: Callable,
    filters: Optional[dict] = None,
) -> list:
    """Embed a query, busca no vector store e mapeia cada hit para um dict.

    Única implementação de "embed + buscar + mapear"; o ranqueamento fica a
    cargo de ``rank_search_results`` no chamador.
    """
    vectors = embedder.embed(query, "search")
    hits = vector_store.search(query=query, vectors=vectors, top_k=top_k, filters=filters)
    return [payload_mapper(h) for h in hits]


# --------------------------------------------------------------------------- #
# Indexação
# --------------------------------------------------------------------------- #
def index_spec_document(
    embedder,
    vector_store,
    *,
    doc_id: UUID,
    content: str,
    project_id: str,
    workspace_id: UUID,
    document_type: str,
    group_id: Optional[str],
    owner: Optional[str] = None,
    updated_at=None,
) -> None:
    """Indexa (upsert por ``doc_id``) a versão vigente de um ``SpecDocument``.

    O payload inclui ``project_id``/``workspace_id``/``document_type``/``group_id``
    (filtros/boosts) e ``owner`` (autor) para o boost de grupo de
    ``rank_search_results``.
    """
    ts = format_utc_iso(updated_at or get_current_utc_time())
    vectors = embedder.embed(content, "add")
    payload = {
        "data": content,
        "content_type": "spec",
        "project": project_id,
        "project_id": project_id,
        "workspace_id": str(workspace_id),
        "document_type": document_type,
        "group_id": group_id,
        "owner": owner,
        "created_at": ts,
        "updated_at": ts,
    }
    # ``doc_id`` como id do ponto: reindexar uma nova versão sobrescreve, não duplica.
    vector_store.insert(vectors=[vectors], payloads=[payload], ids=[str(doc_id)])


def index_completed_workspace(
    db: Session,
    workspace: SpecWorkspace,
    *,
    embedder=None,
    vector_store=None,
) -> int:
    """Gatilho de indexação: indexa cada documento quando o workspace conclui.

    No-op (retorna 0) se o workspace NÃO está em ``concluido`` — a indexação só
    ocorre na transição para concluído, não a cada versão intermediária. Retorna
    o número de documentos indexados.
    """
    if workspace.status != SpecWorkspaceStatus.concluido:
        return 0

    embedder, vector_store = _resolve_backends(embedder, vector_store)
    if embedder is None or vector_store is None:
        logger.warning("spec-index: backend de busca indisponível; indexação adiada")
        return 0

    owner = workspace.created_by
    group_id = group_of_hostname(owner) if owner else None

    docs = db.query(SpecDocument).filter(SpecDocument.workspace_id == workspace.id).all()
    count = 0
    for doc in docs:
        if not doc.current_content:
            continue
        index_spec_document(
            embedder,
            vector_store,
            doc_id=doc.id,
            content=doc.current_content,
            project_id=workspace.project_id,
            workspace_id=workspace.id,
            document_type=doc.document_type.value,
            group_id=group_id,
            owner=owner,
            updated_at=doc.updated_at,
        )
        count += 1
    logger.info("spec-index: %s documento(s) indexado(s) do workspace %s", count, workspace.id)
    return count


# --------------------------------------------------------------------------- #
# Busca
# --------------------------------------------------------------------------- #
def _map_spec_hit(hit) -> dict:
    payload = getattr(hit, "payload", {}) or {}
    return {
        "id": getattr(hit, "id", None),
        "score": getattr(hit, "score", None),
        "content": payload.get("data"),
        "project": payload.get("project") or payload.get("project_id"),
        "workspace_id": payload.get("workspace_id"),
        "document_type": payload.get("document_type"),
        "group_id": payload.get("group_id"),
        "owner": payload.get("owner"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }


def search_specs(
    query: str,
    *,
    project_id: Optional[str] = None,
    requester_group: Optional[str] = None,
    top_k: int = DEFAULT_SPECS_TOP_K,
    embedder=None,
    vector_store=None,
) -> list:
    """Busca semântica em specs concluídas, ordenada por relevância.

    Aplica os mesmos boosts de grupo/projeto de ``rank_search_results``. Como só
    specs concluídas são indexadas, os resultados são inerentemente concluídos.
    ``project_id`` filtra por projeto (comparação normalizada).
    """
    embedder, vector_store = _resolve_backends(embedder, vector_store)
    if embedder is None or vector_store is None:
        return []

    results = semantic_search(
        embedder,
        vector_store,
        query,
        top_k=top_k,
        payload_mapper=_map_spec_hit,
    )

    if project_id:
        target = normalize_project_name(project_id)
        results = [r for r in results if normalize_project_name(r.get("project")) == target]

    rank_search_results(results, preferred_project=project_id, requester_group=requester_group)
    return results
