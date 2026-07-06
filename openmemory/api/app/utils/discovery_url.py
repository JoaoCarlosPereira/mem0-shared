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

_DOCKER_SERVICE_HOSTS = frozenset({"openmemory-mcp", "openmemory_mcp", "mem0_store"})

_DOCKER_BRIDGE_NETS = (
    ipaddress.ip_network("172.17.0.0/16"),
    ipaddress.ip_network("172.18.0.0/16"),
)


def is_docker_bridge_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if not isinstance(addr, ipaddress.IPv4Address):
        return False
    return any(addr in net for net in _DOCKER_BRIDGE_NETS)


def is_unusable_advertise_host(host: str | None) -> bool:
    """True when agents on the LAN cannot reach this host (Docker DNS / bridge IP)."""
    if not host:
        return True
    h = host.strip("[]").lower()
    if h in _DOCKER_SERVICE_HOSTS:
        return True
    try:
        addr = ipaddress.ip_address(h)
    except ValueError:
        return False
    return is_docker_bridge_ip(addr)


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
    """Return the primary private IPv4 of this host, or None.

    Inside Docker the UDP default-route trick often yields a bridge address
    (172.17/172.18.x). Those are skipped in favour of 192.168.x.x / 10.x.x.x
    from ``hostname -I`` when the API runs on the host; in containers the caller
    should set ``OPENMEMORY_DISCOVERY_BASE_URL`` to the host LAN IP.
    """
    candidates: list[str] = []
    try:
        import subprocess

        out = subprocess.check_output(
            ["hostname", "-I"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        candidates.extend(out.strip().split())
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            candidates.append(sock.getsockname()[0])
    except OSError:
        pass
    return _pick_best_lan_ipv4(candidates)


def _pick_best_lan_ipv4(candidates: list[str]) -> str | None:
    ranked: list[tuple[int, str]] = []
    for raw in candidates:
        try:
            addr = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if not isinstance(addr, ipaddress.IPv4Address) or addr.is_loopback or not addr.is_private:
            continue
        if is_docker_bridge_ip(addr):
            score = 0
        elif addr in ipaddress.ip_network("192.168.0.0/16"):
            score = 3
        elif addr in ipaddress.ip_network("10.0.0.0/8"):
            score = 2
        else:
            score = 1
        ranked.append((score, str(addr)))
    if not ranked:
        return None
    best_score, best_ip = max(ranked, key=lambda item: item[0])
    return best_ip if best_score > 0 else None


def url_with_host(url: str, host: str) -> str:
    parts = urlsplit(url)
    port_suffix = f":{parts.port}" if parts.port else ""
    return urlunsplit((parts.scheme, f"{host}{port_suffix}", parts.path, parts.query, parts.fragment))


def ensure_ip_host(url: str) -> str:
    """Replace a DNS hostname with the server's LAN IP when possible."""
    parts = urlsplit(url)
    if is_unusable_advertise_host(parts.hostname):
        lan_ip = detect_lan_ip()
        if lan_ip:
            return url_with_host(url, lan_ip).rstrip("/")
        return url.rstrip("/")

    if is_ip_host(parts.hostname) or is_loopback_host(parts.hostname):
        return url.rstrip("/")

    lan_ip = detect_lan_ip()
    if lan_ip:
        return url_with_host(url, lan_ip).rstrip("/")

    if parts.hostname:
        try:
            resolved = socket.gethostbyname(parts.hostname)
            addr = ipaddress.ip_address(resolved)
            if not addr.is_loopback and not is_docker_bridge_ip(addr):
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
        # Prefer Host header when the ASGI scope carries a resolved IP but the
        # client sent a logical hostname (common in CI and behind proxies).
        host_header = (request.headers.get("host") or "").strip()
        if host_header:
            host_only = host_header.split(":")[0]
            if not is_loopback_host(host_only):
                base = f"{request.url.scheme}://{host_header}".rstrip("/")
            else:
                req_url = str(request.base_url).rstrip("/")
                base = override or req_url
        else:
            req_url = str(request.base_url).rstrip("/")
            if not is_loopback_host(request.url.hostname):
                base = req_url
            else:
                base = override or req_url

    result = ensure_ip_host(base)
    host = urlsplit(result).hostname
    if is_unusable_advertise_host(host):
        if override and not is_loopback_url(override):
            return ensure_ip_host(override)
        lan = detect_lan_ip()
        if lan:
            return url_with_host(result, lan)
    return result
