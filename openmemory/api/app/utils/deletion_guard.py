"""Fail-closed guard against accidental memory deletion.

Memories are durable team knowledge. By default all user-facing delete paths
(API, MCP) are blocked unless explicitly enabled via environment variables.

Infrastructure (``docker compose down -v``) is guarded separately — see
``openmemory/scripts/safe-stack-down.sh``.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class DeletionBlockedError(Exception):
    """Raised when a delete operation is blocked by the deletion guard."""

    def __init__(self, operation: str, *, bulk: bool = False):
        self.operation = operation
        self.bulk = bulk
        if operation.startswith("governance_") or operation in {
            "governance_purge",
            "cold_tier",
        }:
            hint = (
                "Set MEM0_ALLOW_GOVERNANCE_PURGE=1 "
                "(or MEM0_ALLOW_MEMORY_DELETE=1 and MEM0_ALLOW_BULK_DELETE=1) "
                "to enable deliberate governance Qdrant deletes."
            )
        elif bulk:
            hint = (
                "Set MEM0_ALLOW_MEMORY_DELETE=1 and MEM0_ALLOW_BULK_DELETE=1 "
                "to enable deliberate bulk deletes."
            )
        else:
            hint = "Set MEM0_ALLOW_MEMORY_DELETE=1 to enable deliberate deletes."
        super().__init__(f"Memory deletion blocked (operation={operation}). {hint}")


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in _TRUTHY


def memory_delete_allowed() -> bool:
    """True when single or multi-ID deletes are permitted."""
    return _env_flag("MEM0_ALLOW_MEMORY_DELETE", "0")


def bulk_delete_allowed() -> bool:
    """True when delete-all / large bulk deletes are permitted."""
    return memory_delete_allowed() and _env_flag("MEM0_ALLOW_BULK_DELETE", "0")


def governance_purge_allowed() -> bool:
    """True when governance purge/cold-tier may delete Qdrant points.

    Fail-closed: requires either the dedicated ``MEM0_ALLOW_GOVERNANCE_PURGE=1``
    or the same bulk-delete pair used by API/MCP deletes.
    """
    if _env_flag("MEM0_ALLOW_GOVERNANCE_PURGE", "0"):
        return True
    return bulk_delete_allowed()


def assert_memory_delete_allowed(operation: str = "delete") -> None:
    if not memory_delete_allowed():
        raise DeletionBlockedError(operation)


def assert_bulk_delete_allowed(operation: str = "delete_all") -> None:
    if not bulk_delete_allowed():
        raise DeletionBlockedError(operation, bulk=True)


def assert_governance_purge_allowed(operation: str = "governance_purge") -> None:
    if not governance_purge_allowed():
        raise DeletionBlockedError(operation, bulk=True)


def check_memory_delete_allowed(operation: str = "delete") -> str | None:
    """Return an error message when blocked, else None (for MCP string responses)."""
    try:
        assert_memory_delete_allowed(operation)
    except DeletionBlockedError as exc:
        return str(exc)
    return None


def check_bulk_delete_allowed(operation: str = "delete_all") -> str | None:
    try:
        assert_bulk_delete_allowed(operation)
    except DeletionBlockedError as exc:
        return str(exc)
    return None


def deletion_guard_status() -> dict[str, bool]:
    return {
        "memory_delete_allowed": memory_delete_allowed(),
        "bulk_delete_allowed": bulk_delete_allowed(),
        "governance_purge_allowed": governance_purge_allowed(),
    }


def log_deletion_guard_startup() -> None:
    status = deletion_guard_status()
    is_prod = os.environ.get("MEM0_ENV", "").lower() in ("production", "prod")

    if status["memory_delete_allowed"]:
        msg = "MEM0 deletion guard: memory deletes ENABLED (MEM0_ALLOW_MEMORY_DELETE=1)"
        if is_prod:
            logger.error(f"CRITICAL: {msg} IN PRODUCTION ENVIRONMENT!")
        else:
            logger.warning(msg)
    else:
        logger.info(
            "MEM0 deletion guard: memory deletes blocked (default fail-closed)"
        )
    if status["bulk_delete_allowed"]:
        msg = "MEM0 deletion guard: bulk deletes ENABLED (MEM0_ALLOW_BULK_DELETE=1)"
        if is_prod:
            logger.error(f"CRITICAL: {msg} IN PRODUCTION ENVIRONMENT!")
        else:
            logger.warning(msg)
    if status["governance_purge_allowed"]:
        logger.warning(
            "MEM0 deletion guard: governance purge ENABLED "
            "(MEM0_ALLOW_GOVERNANCE_PURGE or bulk delete flags)"
        )
    else:
        logger.info(
            "MEM0 deletion guard: governance purge blocked (default fail-closed)"
        )
