"""Heartbeat do write-worker para detectar fila parada.

O worker atualiza uma chave Redis periodicamente. A API (sempre no ar) usa o
heartbeat para saber se o consumidor morreu/travou sem marcar jobs como
``failed`` — e então materializa a falha na UI para reprocessamento manual.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

HEARTBEAT_KEY = "openmemory:write_worker:heartbeat"
DEFAULT_STALE_SEC = 90


def _redis():
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return None
    try:
        import redis

        return redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    except Exception:  # noqa: BLE001
        logger.warning("write-worker heartbeat: redis unavailable", exc_info=True)
        return None


def beat(meta: Optional[dict[str, Any]] = None) -> None:
    """Record that the write worker is alive (best-effort)."""
    client = _redis()
    if client is None:
        return
    payload = str(time.time())
    if meta:
        # Keep value parseable as float for age; details go in a side key.
        try:
            import json

            client.set(HEARTBEAT_KEY + ":meta", json.dumps(meta), ex=300)
        except Exception:  # noqa: BLE001
            pass
    try:
        client.set(HEARTBEAT_KEY, payload, ex=300)
    except Exception:  # noqa: BLE001
        logger.warning("write-worker heartbeat: set failed", exc_info=True)


def last_beat_age_sec() -> Optional[float]:
    """Seconds since last beat, or ``None`` if unknown / Redis down / no key."""
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(HEARTBEAT_KEY)
    except Exception:  # noqa: BLE001
        return None
    if raw is None:
        return None
    try:
        return max(0.0, time.time() - float(raw))
    except (TypeError, ValueError):
        return None


def heartbeat_key_state() -> str:
    """Return ``ok`` | ``missing`` | ``redis_down`` for stall decisions."""
    client = _redis()
    if client is None:
        return "redis_down"
    try:
        raw = client.get(HEARTBEAT_KEY)
    except Exception:  # noqa: BLE001
        return "redis_down"
    if raw is None:
        return "missing"
    return "ok"


def is_worker_alive(stale_sec: Optional[float] = None) -> bool:
    """True when a recent heartbeat exists.

    If Redis is unavailable we **assume alive** (fail-open) to avoid marking
    healthy queues as failed when Redis is the broken piece. A missing key
    (worker never beat / TTL expired) is treated as dead.
    """
    state = heartbeat_key_state()
    if state == "redis_down":
        return True
    if state == "missing":
        return False
    age = last_beat_age_sec()
    if age is None:
        return False
    limit = float(stale_sec if stale_sec is not None else DEFAULT_STALE_SEC)
    return age <= limit


def worker_status(stale_sec: Optional[float] = None) -> dict[str, Any]:
    """Snapshot for admin UI / stall watchdog."""
    limit = float(stale_sec if stale_sec is not None else DEFAULT_STALE_SEC)
    state = heartbeat_key_state()
    if state == "redis_down":
        return {
            "alive": True,
            "stalled": False,
            "last_heartbeat_age_sec": None,
            "stale_after_sec": limit,
            "heartbeat_state": state,
        }
    if state == "missing":
        return {
            "alive": False,
            "stalled": True,
            "last_heartbeat_age_sec": None,
            "stale_after_sec": limit,
            "heartbeat_state": state,
        }
    age = last_beat_age_sec()
    alive = age is not None and age <= limit
    return {
        "alive": alive,
        "stalled": not alive,
        "last_heartbeat_age_sec": age,
        "stale_after_sec": limit,
        "heartbeat_state": state,
    }
