"""Monkey-patch MCP read tools to record access audit (avoids editing root-owned mcp_server.py)."""

from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)
_installed = False


def _audit_results(
    *,
    project: str | None,
    results: list[dict],
    access_type: str,
    query: str | None = None,
    hostname: str | None = None,
    client_name: str | None = None,
) -> None:
    from app.utils.read_audit import record_memory_reads

    record_memory_reads(
        project=project,
        memory_ids=[r.get("id") for r in results],
        access_type=access_type,
        source="mcp",
        hostname=hostname,
        client_name=client_name,
        query=query,
        items=results,
    )


def _wrap_search(fn: Callable) -> Callable:
    @wraps(fn)
    async def wrapper(query: str, project: str, rerank: bool = False) -> str:
        out = await fn(query, project, rerank=rerank)
        try:
            from app.mcp_server import (
                DEFAULT_CLIENT_NAME,
                client_name_var,
                user_id_var,
            )
            from app.utils.identity import resolve_hostname

            payload = json.loads(out)
            results = payload.get("results") or []
            if isinstance(results, list) and results:
                _audit_results(
                    project=project,
                    results=results,
                    access_type="search",
                    query=query,
                    hostname=resolve_hostname(user_id_var.get(None)),
                    client_name=client_name_var.get(None) or DEFAULT_CLIENT_NAME,
                )
        except Exception:  # noqa: BLE001
            logger.debug("mcp search read-audit skipped", exc_info=True)
        return out

    return wrapper


def _wrap_list(fn: Callable) -> Callable:
    @wraps(fn)
    async def wrapper(project: str) -> str:
        out = await fn(project)
        try:
            from app.mcp_server import (
                DEFAULT_CLIENT_NAME,
                client_name_var,
                user_id_var,
            )
            from app.utils.identity import resolve_hostname

            payload = json.loads(out)
            results = payload.get("results") or []
            if isinstance(results, list) and results:
                _audit_results(
                    project=project,
                    results=results,
                    access_type="list",
                    hostname=resolve_hostname(user_id_var.get(None)),
                    client_name=client_name_var.get(None) or DEFAULT_CLIENT_NAME,
                )
        except Exception:  # noqa: BLE001
            logger.debug("mcp list read-audit skipped", exc_info=True)
        return out

    return wrapper


def install_mcp_read_audit() -> None:
    global _installed
    if _installed:
        return
    try:
        from app import mcp_server as mcp_mod

        mcp_mod.search_memory = _wrap_search(mcp_mod.search_memory)
        mcp_mod.list_memories = _wrap_list(mcp_mod.list_memories)
        _installed = True
        logger.info("MCP read-audit wrappers installed")
    except Exception:  # noqa: BLE001
        logger.warning("could not install MCP read-audit wrappers", exc_info=True)
