"""Tests for discovery base URL resolution (LAN vs localhost)."""

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

_PATH = Path(__file__).resolve().parents[1] / "app" / "utils" / "discovery_url.py"
_spec = importlib.util.spec_from_file_location("discovery_url_under_test", _PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def _request(host: str, port: int = 8765) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/discovery",
        "headers": [],
        "query_string": b"",
        "server": (host, port),
        "scheme": "http",
    }
    return Request(scope)


class TestDiscoveryUrlResolution:
    def test_prefers_non_loopback_env(self):
        req = _request("127.0.0.1")
        with patch.dict(os.environ, {"OPENMEMORY_DISCOVERY_BASE_URL": "http://192.168.3.213:8765/"}):
            assert _mod.resolve_discovery_base_url(req) == "http://192.168.3.213:8765"

    def test_ignores_loopback_env_uses_request_host(self):
        req = _request("192.168.3.213")
        with patch.dict(os.environ, {"OPENMEMORY_DISCOVERY_BASE_URL": "http://localhost:8765"}):
            assert _mod.resolve_discovery_base_url(req) == "http://192.168.3.213:8765"

    def test_falls_back_to_request_when_no_env(self):
        req = _request("memhost")
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENMEMORY_DISCOVERY_BASE_URL", None)
            with patch.object(_mod, "detect_lan_ip", return_value="192.168.3.213"):
                assert _mod.resolve_discovery_base_url(req) == "http://192.168.3.213:8765"

    def test_dns_override_replaced_with_lan_ip(self):
        req = _request("127.0.0.1")
        with patch.dict(
            os.environ,
            {"OPENMEMORY_DISCOVERY_BASE_URL": "http://memorias.sysmo.com.br:8765"},
        ):
            with patch.object(_mod, "detect_lan_ip", return_value="192.168.3.213"):
                assert _mod.resolve_discovery_base_url(req) == "http://192.168.3.213:8765"

    def test_ip_override_is_kept(self):
        req = _request("127.0.0.1")
        with patch.dict(
            os.environ,
            {"OPENMEMORY_DISCOVERY_BASE_URL": "http://192.168.3.213:8765"},
        ):
            assert _mod.resolve_discovery_base_url(req) == "http://192.168.3.213:8765"

    def test_prefers_host_header_over_resolved_ip(self):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/discovery",
            "headers": [(b"host", b"memhost:8765")],
            "query_string": b"",
            "server": ("10.1.0.39", 8765),
            "scheme": "http",
        }
        req = Request(scope)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENMEMORY_DISCOVERY_BASE_URL", None)
            with patch.object(_mod, "detect_lan_ip", return_value="192.168.3.213"):
                assert _mod.resolve_discovery_base_url(req) == "http://192.168.3.213:8765"

    def test_loopback_env_and_request_stays_localhost(self):
        req = _request("127.0.0.1")
        with patch.dict(os.environ, {"OPENMEMORY_DISCOVERY_BASE_URL": "http://localhost:8765"}):
            assert _mod.resolve_discovery_base_url(req) == "http://localhost:8765"
