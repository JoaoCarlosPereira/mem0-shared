"""Resolução do grupo de um autor a partir do hostname (task_02 / ADR-003).

A priorização por grupo na busca precisa saber, para cada resultado, o **grupo atual**
do autor (identificado pelo ``hostname`` gravado no payload do vetor). Resolver isso no
momento da leitura — em vez de persistir o grupo no payload — preserva a associação
**dinâmica** (mover um usuário de grupo re-contextualiza todas as suas memórias).

Para não consultar o banco a cada resultado, o mapa ``hostname → grupo`` é cacheado em
memória com TTL curto. Ao mudar o grupo de um usuário (gestão de membros no Admin), o
cache deve ser invalidado via :func:`invalidate_group_cache`.

A resolução é **best-effort**: qualquer falha resulta em ``None`` (tratado como neutro
pelo ranqueamento), nunca em exceção no caminho de leitura.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

from app.utils.identity import resolve_hostname

# TTL do cache em segundos. Curto por padrão: equilibra carga no banco e frescor após
# uma mudança de grupo que não tenha invalidado o cache explicitamente.
GROUP_CACHE_TTL_SECONDS = float(os.getenv("MEM0_GROUP_CACHE_TTL_SECONDS", "30"))

# Cache simples ``hostname -> (group_name | None, expires_at)`` protegido por lock,
# pois a busca resolve grupos a partir de threads (anyio.to_thread).
_cache: dict[str, tuple[Optional[str], float]] = {}
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _query_group_name(hostname: str) -> Optional[str]:
    """Consulta o nome do grupo atual do usuário cujo ``user_id`` == hostname."""
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == hostname).first()
        if user is None or user.group is None:
            return None
        return user.group.name
    finally:
        db.close()


def group_of_hostname(hostname: Optional[str]) -> Optional[str]:
    """Nome do grupo atual do autor identificado por ``hostname``.

    Retorna ``None`` quando o hostname é vazio, o usuário não existe, não tem grupo,
    ou em caso de qualquer falha de resolução (nunca levanta no caminho de leitura).
    Usa cache em memória com TTL curto.
    """
    if not hostname:
        return None
    key = resolve_hostname(hostname)

    now = _now()
    with _lock:
        cached = _cache.get(key)
        if cached is not None and cached[1] > now:
            return cached[0]

    try:
        name = _query_group_name(key)
    except Exception:  # noqa: BLE001 - resolução é best-effort no read
        return None

    with _lock:
        _cache[key] = (name, _now() + GROUP_CACHE_TTL_SECONDS)
    return name


def requester_group_for_mcp(hostname: Optional[str]) -> Optional[str]:
    """Garante cadastro e retorna o grupo do usuário (leitura/escrita MCP).

    Não lê ``?group=`` — usa apenas ``users.group_id`` já vinculado na instalação.
    """
    ensure_user_registered(hostname)
    return group_of_hostname(hostname)


def invalidate_group_cache(hostname: Optional[str] = None) -> None:
    """Invalida o cache de grupos.

    Sem argumento, limpa todo o cache (uso típico após mudanças de membros no Admin).
    Com ``hostname``, invalida apenas a entrada correspondente.
    """
    with _lock:
        if hostname is None:
            _cache.clear()
        else:
            _cache.pop(resolve_hostname(hostname), None)


def normalize_group_name(name: Optional[str]) -> Optional[str]:
    """Normaliza o nome de grupo: ``trim``; retorna ``None`` se vazio.

    Usado tanto na leitura do parâmetro de instalação (task_05) quanto no CRUD do
    Admin (task_06) para que a comparação de nomes seja consistente.
    """
    if not name:
        return None
    trimmed = str(name).strip()
    return trimmed or None


def get_or_create_group(db, name: Optional[str]):
    """Retorna o ``Group`` com ``name`` (comparação case-insensitive), criando se faltar.

    Nome ausente/vazio recai no grupo Default. Não faz commit — o chamador controla a
    transação.
    """
    from app.models import DEFAULT_GROUP_NAME, Group
    from sqlalchemy import func

    target = normalize_group_name(name) or DEFAULT_GROUP_NAME
    group = (
        db.query(Group)
        .filter(func.lower(Group.name) == target.lower())
        .first()
    )
    if group is None:
        group = Group(name=target)
        db.add(group)
        db.flush()
    return group


def ensure_user_registered(hostname: Optional[str]) -> None:
    """Garante cadastro do hostname com Default se ainda não tiver grupo.

    Usado em leitura/escrita MCP (sem ``?group=`` na URL). Não sobrescreve grupo existente.
    """
    ensure_user_group(hostname, None)


def ensure_user_group(hostname: Optional[str], group_name: Optional[str] = None) -> None:
    """Vincula o hostname a um grupo na **primeira conexão** (instalação do plugin).

    O ``group_name`` da URL ``?group=`` (instalação) é aplicado **somente** quando o
    usuário ainda não tem grupo (criação ou linha sem ``group_id``). Reconexões e o
    Admin prevalecem — não sobrescrevem ajustes posteriores. Ausente recai no Default.
    Best-effort: falhas não derrubam a conexão MCP.
    """
    key = resolve_hostname(hostname)
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == key).first()
        if user is not None and user.group_id is not None:
            return
        group = get_or_create_group(db, group_name)
        if user is None:
            user = User(user_id=key, group_id=group.id)
            db.add(user)
        else:
            user.group_id = group.id
        db.commit()
        invalidate_group_cache(key)
    except Exception:  # noqa: BLE001 - upsert de grupo é best-effort no connect
        db.rollback()
    finally:
        db.close()
