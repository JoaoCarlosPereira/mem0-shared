"""Recency-weighted ordering for read paths (ADR-003 applied at read time).

Shared by ``app.mcp_server`` (MCP tools) and ``app.routers.compat_v3`` (the REST
shim the plugin hooks call) so both read paths order results the same way and
share a single calibration point (the env vars below).

Recency is measured from ``updated_at`` (the last time the fact changed) and falls
back to ``created_at``. A fact created long ago but updated recently is therefore
treated as recent, so a newer correction outranks the stale version it supersedes
— even when the older one is a closer semantic match.

Tunable via env:
  MEM0_SEARCH_RECENCY_HALFLIFE_DAYS — days for the recency weight to halve (time scale)
  MEM0_SEARCH_RECENCY_WEIGHT        — how strongly recency influences order
                                      (0.0 = pure semantic relevance, previous behavior)
  MEM0_SEARCH_PROJECT_BOOST_EXACT   — multiplicative boost when project names match exactly
  MEM0_SEARCH_PROJECT_BOOST_FUZZY   — smaller boost when normalized names overlap/substring-match
"""

from __future__ import annotations

import datetime
import os
from typing import Optional

from app.utils.groups import group_of_hostname

SEARCH_RECENCY_HALFLIFE_DAYS = float(os.getenv("MEM0_SEARCH_RECENCY_HALFLIFE_DAYS", "90"))
SEARCH_RECENCY_WEIGHT = float(os.getenv("MEM0_SEARCH_RECENCY_WEIGHT", "1.0"))
SEARCH_PROJECT_BOOST_EXACT = float(os.getenv("MEM0_SEARCH_PROJECT_BOOST_EXACT", "0.1"))
SEARCH_PROJECT_BOOST_FUZZY = float(os.getenv("MEM0_SEARCH_PROJECT_BOOST_FUZZY", "0.05"))

# Multiplicador forte aplicado quando o autor da memória pertence ao mesmo grupo do
# solicitante (ADR-003). Forte por padrão: prioriza o contexto da própria equipe sem
# remover memórias de outros grupos. Calibrável por env, sem alteração de código.
SEARCH_GROUP_BOOST = float(os.getenv("MEM0_SEARCH_GROUP_BOOST", "2.5"))


def parse_ts(value):
    """Parse an ISO-8601 timestamp into an aware UTC datetime, or None."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def recency_factor(result, now):
    """Exponential decay in (0, 1] from a fact's last-change time.

    Uses ``updated_at`` and falls back to ``created_at``. Returns 1.0 (neutral, no
    penalty) when neither timestamp is parseable or recency is disabled, so undated
    facts rank by pure relevance instead of being unfairly buried.
    """
    if SEARCH_RECENCY_HALFLIFE_DAYS <= 0:
        return 1.0
    ts = parse_ts(result.get("updated_at")) or parse_ts(result.get("created_at"))
    if ts is None:
        return 1.0
    age_days = max(0.0, (now - ts).total_seconds() / 86400.0)
    return 0.5 ** (age_days / SEARCH_RECENCY_HALFLIFE_DAYS)


def normalize_project_name(name) -> str:
    """Normalize project identifiers for fuzzy comparison (case/punctuation insensitive)."""
    if not name:
        return ""
    return "".join(c for c in str(name).lower() if c.isalnum())


def project_match_factor(result_project, preferred_project) -> float:
    """Small boost for matching project names; never penalizes mismatches."""
    if not preferred_project:
        return 1.0
    result_norm = normalize_project_name(result_project)
    preferred_norm = normalize_project_name(preferred_project)
    if not preferred_norm:
        return 1.0
    if result_norm == preferred_norm:
        return 1.0 + SEARCH_PROJECT_BOOST_EXACT
    if result_norm and (result_norm in preferred_norm or preferred_norm in result_norm):
        return 1.0 + SEARCH_PROJECT_BOOST_FUZZY
    return 1.0


def group_match_factor(author_group, requester_group) -> float:
    """Boost forte quando autor e solicitante são do mesmo grupo; neutro caso contrário.

    Retorna :data:`SEARCH_GROUP_BOOST` somente quando ambos os grupos estão presentes e
    são iguais. Resultados sem grupo de autor resolvível (ex.: memórias legadas sem
    ``hostname`` no payload) ou solicitante sem grupo recebem ``1.0`` — nunca penalizados.
    """
    if not requester_group or not author_group:
        return 1.0
    return SEARCH_GROUP_BOOST if author_group == requester_group else 1.0


def rank_search_results(results, preferred_project=None, requester_group=None):
    """Order results by semantic score blended with recency, project and group boost.

    Relevance and recency dominate ordering; ``preferred_project`` applies a small
    multiplicative boost when names match. When ``requester_group`` is provided, results
    whose author belongs to the same group receive a strong multiplicative boost
    (ADR-003). The author group is resolved dynamically from each result's ``owner``
    (the author hostname); reads remain global — group only affects ordering. Missing
    project/owner/group never penalizes a result.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    def _project_name(result) -> Optional[str]:
        name = result.get("project")
        if name:
            return str(name)
        meta = result.get("metadata")
        if isinstance(meta, dict) and meta.get("project"):
            return str(meta["project"])
        return None

    def _author_group(result) -> Optional[str]:
        if not requester_group:
            return None  # sem solicitante com grupo, evita lookups desnecessários
        return group_of_hostname(result.get("owner"))

    def key(r):
        score = r.get("score")
        score = score if isinstance(score, (int, float)) else 0.0
        factor = recency_factor(r, now) ** SEARCH_RECENCY_WEIGHT
        factor *= project_match_factor(_project_name(r), preferred_project)
        factor *= group_match_factor(_author_group(r), requester_group)
        return score * factor

    results.sort(key=key, reverse=True)
    return results


def recency_weighted_sort(results):
    """Order results in place by semantic score blended with recency.

    Backward-compatible alias for ``rank_search_results`` without project/group boost.
    """
    return rank_search_results(results)
