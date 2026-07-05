"""Resolve the base URL advertised in /discovery and /provision.

Remote agents on the LAN must receive a reachable host (the memory server's
private IP), not ``localhost`` or a DNS hostname. Priority:

1. ``OPENMEMORY_DISCOVERY_BASE_URL`` when it points at a non-loopback host
2. The incoming request host when it is non-loopback (client reached us by IP)
3. The env override or request URL as a last resort

The returned URL always uses an IPv4 literal when a private LAN address can be
detected, so install commands and MCP links never show a DNS name.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit, urlunsplit

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


def is_ip_host(host: str | None) -> bool:
    if not host:
        return False
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def detect_lan_ip() -> str | None:
    """Return the primary private IPv4 of this host, or None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        if ipaddress.ip_address(ip).is_private:
            return ip
    except OSError:
        pass
    return None


def url_with_host(url: str, host: str) -> str:
    parts = urlsplit(url)
    port_suffix = f":{parts.port}" if parts.port else ""
    return urlunsplit((parts.scheme, f"{host}{port_suffix}", parts.path, parts.query, parts.fragment))


def ensure_ip_host(url: str) -> str:
    """Replace a DNS hostname with the server's LAN IP when possible."""
    parts = urlsplit(url)
    if is_ip_host(parts.hostname) or is_loopback_host(parts.hostname):
        return url.rstrip("/")

    lan_ip = detect_lan_ip()
    if lan_ip:
        return url_with_host(url, lan_ip).rstrip("/")

    if parts.hostname:
        try:
            resolved = socket.gethostbyname(parts.hostname)
            if not ipaddress.ip_address(resolved).is_loopback:
                return url_with_host(url, resolved).rstrip("/")
        except OSError:
            pass

    return url.rstrip("/")


def resolve_discovery_base_url(request: Request) -> str:
    """Return the LAN-reachable base URL for MCP/discovery/provision payloads."""
    override = (os.getenv("OPENMEMORY_DISCOVERY_BASE_URL") or "").strip().rstrip("/")
    if override and not is_loopback_url(override):
        base = override
    else:
        req_url = str(request.base_url).rstrip("/")
        if not is_loopback_host(request.url.hostname):
            base = req_url
        else:
            base = override or req_url

    return ensure_ip_host(base)
