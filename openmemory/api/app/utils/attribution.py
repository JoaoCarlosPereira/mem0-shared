"""Attribution helpers for memory payloads (ADR-003).

Write paths may store the author as ``hostname`` (MCP queue worker) or as
``user_id`` (compat_v3 / plugin hooks via mem0 SDK). Read paths must resolve
both consistently so UIs and MCP clients never fall back to the *requester's*
connection identity when the real author is present in the payload.
"""

from __future__ import annotations

from typing import Any, Optional

from app.utils.identity import resolve_hostname


def author_hostname_from_payload(payload: Optional[dict[str, Any]]) -> Optional[str]:
    """Return the author hostname from a Qdrant/mem0 vector payload.

    Prefers explicit ``hostname`` (MCP write worker), then ``user_id`` (SDK /
    compat_v3 hook writes). Returns ``None`` when neither is present.
    """
    if not payload:
        return None
    raw = payload.get("hostname") or payload.get("user_id")
    if not raw:
        return None
    resolved = resolve_hostname(str(raw))
    if resolved == "unknown-host":
        return None
    return resolved


def attribution_from_payload(payload: dict[str, Any]) -> dict[str, Optional[str]]:
    """Extract write-time attribution stored in a vector payload."""
    hostname = author_hostname_from_payload(payload)
    client = payload.get("mcp_client")
    return {
        "created_by_hostname": hostname,
        "created_by_client": str(client) if client else None,
    }
