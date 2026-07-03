"""Validação e cache dos tokens de agente (feature auth Google, ADR-003/ADR-006).

O token viaja como ``?token=`` na URL MCP (ADR-003) e é resolvido aqui para o
dono (pessoa) via hash SHA-256 contra ``agent_tokens``. O lookup usa cache
Redis com TTL curto e cai para o banco quando o Redis está indisponível —
falha de infraestrutura nunca derruba a requisição por si só, apenas o token
inválido nega acesso.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

AGENT_TOKEN_PREFIX = "omtk_"
CACHE_TTL_SECONDS = 60
_CACHE_KEY_TEMPLATE = "agent_token:{digest}"
# Prefixo exibível: "omtk_" + 4 primeiros chars do segredo (não-secreto, serve
# para o usuário identificar o token no painel sem revelar o valor).
_DISPLAY_PREFIX_LEN = len(AGENT_TOKEN_PREFIX) + 4


def hash_token(raw: str) -> str:
    """SHA-256 hex do token em claro (única forma persistida/cacheada)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token() -> Tuple[str, str]:
    """Gera um token de agente imprevisível (CSPRNG).

    Retorna ``(token_em_claro, prefixo_exibivel)``. O valor em claro só existe
    na resposta de criação — persistir apenas ``hash_token(raw)`` + prefixo.
    """
    raw = AGENT_TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[:_DISPLAY_PREFIX_LEN]


def _redis_client():
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis

        return redis.from_url(url, socket_timeout=0.2, socket_connect_timeout=0.2)
    except Exception:  # noqa: BLE001 — Redis indisponível => fallback ao banco
        return None


def resolve_agent_token(raw_token: str) -> Optional[str]:
    """Resolve o token em claro para o ``user_id`` (str UUID) do dono ativo.

    Retorna ``None`` para token desconhecido ou revogado. Cache Redis apenas de
    resultados válidos (revogação invalida via ``invalidate_agent_token_cache``).
    """
    digest = hash_token(raw_token)
    cache_key = _CACHE_KEY_TEMPLATE.format(digest=digest)

    client = _redis_client()
    if client is not None:
        try:
            cached = client.get(cache_key)
            if cached:
                return cached.decode("utf-8") if isinstance(cached, bytes) else str(cached)
        except Exception:  # noqa: BLE001
            logger.debug("cache de token de agente indisponível; usando banco")

    from app.database import SessionLocal
    from app.models import AgentToken

    db = SessionLocal()
    try:
        row = (
            db.query(AgentToken)
            .filter(
                AgentToken.token_hash == digest,
                AgentToken.revoked_at.is_(None),
            )
            .first()
        )
        if row is None:
            return None
        user_id = str(row.user_id)
    finally:
        db.close()

    if client is not None:
        try:
            client.set(cache_key, user_id, ex=CACHE_TTL_SECONDS)
        except Exception:  # noqa: BLE001
            pass
    return user_id


def invalidate_agent_token_cache(token_hash: str) -> None:
    """Remove o hash do cache (chamado na revogação/rotação — task_04)."""
    client = _redis_client()
    if client is None:
        return
    try:
        client.delete(_CACHE_KEY_TEMPLATE.format(digest=token_hash))
    except Exception:  # noqa: BLE001
        logger.debug("falha ao invalidar cache de token de agente (best-effort)")
