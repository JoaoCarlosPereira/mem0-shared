"""Resolve the base URL advertised in /discovery and /provision.

Remote agents on the LAN must receive a reachable host (the memory server's
private IP), not ``localhost``. Priority:

1. ``OPENMEMORY_DISCOVERY_BASE_URL`` when it points at a non-loopback host
2. The incoming request host when it is non-loopback (client reached us by IP)
3. The env override or request URL as a last resort
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

from fastapi import Request

_LOOPBACK_NAMES = frozenset({"localhost"})


def is_loopback_host(host: str | None) -> bool:
    if not host:
        return True
    h = host.strip("[]").lower()
    if h in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def is_loopback_url(url: str) -> bool:
    return is_loopback_host(urlsplit(url).hostname)


def resolve_discovery_base_url(request: Request) -> str:
    """Return the LAN-reachable base URL for MCP/discovery/provision payloads."""
    override = (os.getenv("OPENMEMORY_DISCOVERY_BASE_URL") or "").strip().rstrip("/")
    if override and not is_loopback_url(override):
        return override

    # Prefer the HTTP Host header: clients (and httpx in CI) may resolve a
    # hostname to an IP in the request URL while still sending the logical name
    # in Host — advertising the header keeps discovery stable across DNS setups.
    host_header = (request.headers.get("host") or "").strip()
    if host_header:
        host_only = host_header.split(":")[0]
        if not is_loopback_host(host_only):
            return f"{request.url.scheme}://{host_header}".rstrip("/")

    req_url = str(request.base_url).rstrip("/")
    if not is_loopback_host(request.url.hostname):
        return req_url

    return override or req_url
