"""Resolução dinâmica hostname→pessoa (feature auth Google, ADR-005).

Os payloads do Qdrant permanecem com ``hostname``; a atribuição a uma pessoa é
resolvida em tempo de consulta via ``machines.linked_user_id``. Mesmo contrato
do cache de grupos (``app.utils.groups``): TTL curto, thread-safe, best-effort
(falha ⇒ ``None``, nunca exceção no caminho de leitura) e invalidação explícita
no commit de vínculo/desvínculo.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

from app.utils.identity import resolve_hostname

IDENTITY_LINK_CACHE_TTL_SECONDS = float(
    os.getenv("MEM0_IDENTITY_LINK_CACHE_TTL_SECONDS", "30")
)

# hostname -> (user_id str | None, expires_at)
_cache: dict[str, tuple[Optional[str], float]] = {}
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _query_linked_person(hostname: str) -> Optional[str]:
    from app.database import SessionLocal
    from app.models import Machine, MachineStatus

    db = SessionLocal()
    try:
        machine = (
            db.query(Machine)
            .filter(
                Machine.hostname == hostname,
                Machine.status == MachineStatus.linked,
                Machine.linked_user_id.isnot(None),
            )
            .first()
        )
        return str(machine.linked_user_id) if machine is not None else None
    finally:
        db.close()


def resolve_person_for_hostname(hostname: Optional[str]) -> Optional[str]:
    """``users.id`` (str UUID) da pessoa vinculada à máquina, ou ``None``.

    ``None`` para hostname vazio, máquina desconhecida/não vinculada/em conflito
    ou qualquer falha de resolução (best-effort no caminho de leitura).
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
        person = _query_linked_person(key)
    except Exception:  # noqa: BLE001 - resolução é best-effort
        return None

    with _lock:
        _cache[key] = (person, _now() + IDENTITY_LINK_CACHE_TTL_SECONDS)
    return person


def invalidate_identity_link_cache(hostname: Optional[str] = None) -> None:
    """Invalida o cache (tudo, ou apenas o hostname informado)."""
    with _lock:
        if hostname is None:
            _cache.clear()
        else:
            _cache.pop(resolve_hostname(hostname), None)
