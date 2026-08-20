"""Optional cross-encoder reranking for the MCP semantic read path.

``search_memory`` has always accepted a ``rerank`` flag, but nothing was wired to
it: the parameter was declared and never read, so callers asking for reranking
silently got plain vector order. This module supplies the wiring and — just as
importantly — makes the outcome observable, so a caller can tell whether
reranking actually happened.

Configuration (all optional; when unset, reranking is simply not available):
  MEM0_RERANKER_PROVIDER — cohere | sentence_transformer | huggingface |
                           zero_entropy | llm_reranker
  MEM0_RERANKER_MODEL    — provider-specific model id
  MEM0_RERANKER_API_KEY  — for providers that need one

Scores: cross-encoders emit unbounded logits, which cannot be fed to the
multiplicative recency/project/group boosts in :mod:`app.utils.recency` — a
negative logit multiplied by a boost moves the wrong way. We therefore min-max
normalize the rerank scores over the candidate pool into ``score`` (the field the
ranker consumes), while preserving the untouched values in ``semantic_score`` and
``rerank_score`` for inspection.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_reranker = None
_load_error: Optional[str] = None
_loaded = False


def reranker_provider() -> str:
    return (os.getenv("MEM0_RERANKER_PROVIDER") or "").strip()


def _build_reranker():
    """Instantiate the configured reranker, or return None when unavailable."""
    provider = reranker_provider()
    if not provider:
        return None, "not_configured"

    config: dict[str, Any] = {"provider": provider}
    model = (os.getenv("MEM0_RERANKER_MODEL") or "").strip()
    if model:
        config["model"] = model
    api_key = (os.getenv("MEM0_RERANKER_API_KEY") or "").strip()
    if api_key:
        config["api_key"] = api_key

    try:
        from mem0.utils.factory import RerankerFactory

        return RerankerFactory.create(provider, config), None
    except Exception as exc:  # noqa: BLE001 - never break search over reranking
        logger.warning("reranker '%s' unavailable: %s", provider, exc)
        return None, f"unavailable: {exc}"


def get_reranker():
    """Lazily build the reranker once; cache the instance and any load failure."""
    global _reranker, _load_error, _loaded
    if _loaded:
        return _reranker, _load_error
    with _lock:
        if not _loaded:
            _reranker, _load_error = _build_reranker()
            _loaded = True
    return _reranker, _load_error


def reset_reranker_cache() -> None:
    """Drop the cached instance (tests / config reload)."""
    global _reranker, _load_error, _loaded
    with _lock:
        _reranker = None
        _load_error = None
        _loaded = False


def rerank_config_status() -> dict:
    """Operator-facing status: whether rerank is configured and usable.

    Does not load the model unless already cached — reports env + cache state.
    """
    provider = reranker_provider() or None
    configured = bool(provider)
    if not configured:
        return {
            "configured": False,
            "provider": None,
            "reason": "not_configured",
        }
    if _loaded:
        if _reranker is None:
            return {
                "configured": True,
                "provider": provider,
                "reason": _load_error or "unavailable",
            }
        return {
            "configured": True,
            "provider": provider,
            "reason": None,
        }
    return {
        "configured": True,
        "provider": provider,
        "reason": "not_loaded_yet",
    }


def _normalize_into_score(results: list[dict]) -> None:
    """Map ``rerank_score`` onto ``score`` in [0, 1], preserving the originals.

    A flat pool (every document scored alike) carries no ordering information, so
    every entry gets 1.0 and the recency/project/group boosts decide alone.
    """
    scores = [
        r["rerank_score"]
        for r in results
        if isinstance(r.get("rerank_score"), (int, float))
    ]
    if not scores:
        return
    lo, hi = min(scores), max(scores)
    span = hi - lo
    for r in results:
        raw = r.get("rerank_score")
        if not isinstance(raw, (int, float)):
            continue
        r.setdefault("semantic_score", r.get("score"))
        r["score"] = 1.0 if span <= 0 else (raw - lo) / span


def apply_rerank(query: str, results: list[dict]) -> dict:
    """Rerank ``results`` in place when a reranker is configured.

    Returns a status dict that the caller must surface to the client, so that
    "I asked for rerank" and "rerank happened" are never conflated. Any failure
    degrades to the original ordering — reranking must not break search.
    """
    provider = reranker_provider()
    if not results:
        return {"applied": False, "provider": provider or None, "reason": "no_results"}

    reranker, load_error = get_reranker()
    if reranker is None:
        return {
            "applied": False,
            "provider": provider or None,
            "reason": load_error or "not_configured",
        }

    # Defensive copy: the caller's list may hold dicts shared with the read cache,
    # and not every provider copies before writing ``rerank_score``.
    candidates = [dict(r) for r in results]

    try:
        # top_k=None: reranking orders the whole candidate pool; the caller still
        # applies the recency/project/group boosts and cuts the page afterwards.
        reranked = reranker.rerank(query, candidates, top_k=None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rerank failed (provider=%s): %s", provider, exc)
        return {"applied": False, "provider": provider, "reason": f"failed: {exc}"}

    if not reranked:
        return {"applied": False, "provider": provider, "reason": "empty_result"}

    _normalize_into_score(reranked)
    results[:] = reranked
    return {"applied": True, "provider": provider, "reranked": len(reranked)}
