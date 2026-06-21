"""MCP connection auto-discovery endpoint (task_08 / ADR-005).

Exposes a GET endpoint that returns a ready-to-use MCP connection config as
JSON so agents can self-configure without manual setup. The payload mirrors the
real MCP route registered in ``app.mcp_server`` (``/mcp/{client_name}/sse/{user_id}``
and the Streamable HTTP variant) and the field semantics defined by tasks 04/07:
``user_id`` carries the machine hostname (attribution only) and ``project`` is
required and scopes the memory.

The ``base_url`` is the LAN-reachable address of this memory server (see
``app.utils.discovery_url``), not ``localhost``, so remote agents can connect.
"""

from fastapi import APIRouter, Request

from app.utils.discovery_url import resolve_discovery_base_url

router = APIRouter(prefix="", tags=["discovery"])

# Route templates of the MCP transports registered in app.mcp_server. Kept in
# sync with the `/mcp` router there; the segments are the fields the agent fills.
_SSE_ROUTE_TEMPLATE = "/mcp/{client_name}/sse/{user_id}"
_HTTP_ROUTE_TEMPLATE = "/mcp/{client_name}/http/{user_id}"

# Default transport advertised at the top level (SSE remains the widely-supported
# default); both enabled transports are listed under "transports".
_DEFAULT_TRANSPORT = "sse"


def _discovery_payload(request: Request) -> dict:
    return {
        "transport": _DEFAULT_TRANSPORT,
        "base_url": resolve_discovery_base_url(request),
        "route_template": _SSE_ROUTE_TEMPLATE,
        "transports": {
            "sse": _SSE_ROUTE_TEMPLATE,
            "http": _HTTP_ROUTE_TEMPLATE,
        },
        "fields": {
            "client_name": "MCP client/agent name",
            "user_id": "hostname",
            "project": "obrigatório",
        },
    }


@router.get("/discovery")
async def get_discovery(request: Request) -> dict:
    """Return the MCP connection config as JSON for agent self-configuration."""
    return _discovery_payload(request)


@router.get("/.well-known/mcp")
async def get_well_known_mcp(request: Request) -> dict:
    """Alias of :func:`get_discovery` on the conventional well-known path."""
    return _discovery_payload(request)
