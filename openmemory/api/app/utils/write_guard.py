"""Fail-closed guard against writes from unregistered machines/users.

Memory writes via MCP require a registered identity: a valid hostname that
exists in ``users.user_id``, or a valid agent token (``?token=``) whose owner
exists. Hostnames that resolve to ``unknown-host`` or are absent from the user
registry are rejected unless explicitly allowed via environment variable.

Google/machine linking is **not** required for writes — only that the hostname
user row exists (typically created on first MCP connection or Admin setup).
"""

from __future__ import annotations

import logging
import os
import uuid

from app.utils.identity import DEFAULT_HOSTNAME, resolve_hostname

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class WriteBlockedError(Exception):
    """Raised when a memory write is blocked by the write guard."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in _TRUTHY


def unregistered_writes_allowed() -> bool:
    """True when writes from unknown or unregistered hostnames are permitted."""
    return _env_flag("MEM0_ALLOW_UNREGISTERED_WRITES", "0")


def _user_exists_by_id(user_id: str) -> bool:
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return False

    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_uuid).first() is not None
    except Exception:  # noqa: BLE001
        return False
    finally:
        db.close()


def _hostname_user_exists(hostname: str) -> bool:
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        return db.query(User).filter(User.user_id == hostname).first() is not None
    except Exception:  # noqa: BLE001
        return False
    finally:
        db.close()


def assert_write_allowed(
    hostname: str | None,
    *,
    auth_method: str | None = None,
    auth_user: str | None = None,
) -> None:
    """Raise :class:`WriteBlockedError` when the write identity is not registered."""
    if unregistered_writes_allowed():
        return

    method = (auth_method or "").strip()
    person = (auth_user or "").strip()
    if method == "agent_token" and person:
        if _user_exists_by_id(person):
            return
        raise WriteBlockedError(
            "memory write blocked — agent token owner not found"
        )

    resolved = resolve_hostname(hostname)
    if resolved == DEFAULT_HOSTNAME:
        raise WriteBlockedError(
            "memory write blocked — hostname not identified (unknown-host). "
            "Configure MCP with ${env:COMPUTERNAME}."
        )

    if not _hostname_user_exists(resolved):
        raise WriteBlockedError(
            f"memory write blocked — user '{resolved}' is not registered. "
            "Connect once to OpenMemory (MCP install) or ask an admin to add the hostname."
        )


def check_write_allowed(
    hostname: str | None,
    *,
    auth_method: str | None = None,
    auth_user: str | None = None,
) -> str | None:
    """Return an MCP error string when blocked, else ``None``."""
    try:
        assert_write_allowed(
            hostname,
            auth_method=auth_method,
            auth_user=auth_user,
        )
    except WriteBlockedError as exc:
        return f"Error: {exc}"
    return None


def write_guard_status() -> dict[str, bool]:
    allowed = unregistered_writes_allowed()
    return {
        "unregistered_writes_allowed": allowed,
        "write_guard_active": not allowed,
    }


def log_write_guard_startup() -> None:
    status = write_guard_status()
    if status["unregistered_writes_allowed"]:
        logger.warning(
            "MEM0 write guard: unregistered writes ENABLED "
            "(MEM0_ALLOW_UNREGISTERED_WRITES=1)"
        )
    else:
        logger.info(
            "MEM0 write guard: unregistered writes blocked (default fail-closed)"
        )
