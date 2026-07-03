"""
MCP Server for OpenMemory with resilient memory client handling.

This module implements an MCP (Model Context Protocol) server that provides
memory operations for OpenMemory. The memory client is initialized lazily
to prevent server crashes when external dependencies (like Ollama) are
unavailable. If the memory client cannot be initialized, the server will
continue running with limited functionality and appropriate error messages.

Key features:
- Lazy memory client initialization
- Graceful error handling for unavailable dependencies
- Fallback to database-only mode when vector store is unavailable
- Proper logging for debugging connection issues
- Environment variable parsing for API keys
"""

import contextvars
import datetime
import hashlib
import json
import logging
import time
import uuid

import anyio

from app.database import SessionLocal
from app.models import (
    Memory,
    MemoryAccessLog,
    MemoryState,
    MemoryStatusHistory,
    WriteAuditLog,
)
from app.utils.metrics import (
    EMBED_CACHE_HIT,
    EMBED_CACHE_MISS,
    SEARCH_CACHE_HIT,
    SEARCH_CACHE_MISS,
    SEARCH_LATENCY,
)
from app.utils.env import safe_load_dotenv
from app.utils.db import get_user_and_app
from app.utils.groups import ensure_user_group, ensure_user_registered, requester_group_for_mcp
from app.utils.identity import resolve_hostname
from app.utils.logging_context import auth_method_var, auth_user_var
from app.utils.memory import get_memory_client_safe
from app.utils.partitioning import bind_active_collection
from app.utils.permissions import check_memory_access_permissions
from app.utils.read_cache import read_cache
from app.utils.recency import rank_search_results
from app.utils.token_usage_wrapper import usage_attribution
from app.utils.write_queue import WriteJob, write_queue
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import Response

# Load environment variables
safe_load_dotenv()

# Initialize MCP
mcp = FastMCP("mem0-mcp-server")

# get_memory_client_safe is imported from app.utils.memory (canonical location).

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Read-path defaults (task_03 / ADR-003): keep top_k bounded so project-scoped
# reads stay low-latency on the single shared collection.
DEFAULT_SEARCH_TOP_K = 20
DEFAULT_LIST_TOP_K = 20

# Write-path default (task_07): the MCP route always provides a client_name, but
# a direct tool call may not — fall back to an explicit sentinel for attribution.
DEFAULT_CLIENT_NAME = "unknown-client"

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Save content for asynchronous memory extraction in a project. Call this whenever the user shares durable facts or preferences, or asks you to remember something. `project` is REQUIRED and scopes the memory (memories are shared across all machines on the local network). Returns immediately with status accepted — processing is fire-and-forget on the server. Do NOT poll for job status or wait for completion; use search_memory later if needed.")
async def add_memories(text: str, project: str) -> str:
    # task_07 / ADR-004: non-blocking write. We validate the input, enqueue the
    # job and return an immediate accepted ack (no job_id exposed to agents). The slow LLM extraction and
    # persistence are performed out of band by the background worker (task_06),
    # so the LLM/memory client is intentionally NOT touched on this request path.
    #
    # The hostname (from the user_id slot) is attribution only (ADR-003); it is
    # carried on the job and never used as a read filter. client_name records the
    # originating MCP client/agent.
    hostname = resolve_hostname(user_id_var.get(None))
    client_name = client_name_var.get(None) or DEFAULT_CLIENT_NAME

    # Garante cadastro do hostname; grupo vem de users.group_id (Admin), não da URL.
    ensure_user_registered(hostname)

    if not text or not text.strip():
        return "Error: text not provided"
    if not project or not project.strip():
        return "Error: project not provided"

    project = project.strip()

    try:
        job_id = write_queue.enqueue(
            WriteJob(
                id="",
                project=project,
                hostname=hostname,
                client_name=client_name,
                text=text,
                created_at="",
            )
        )
    except Exception as e:
        logging.exception(f"Error enqueuing memory write: {e}")
        return f"Error enqueuing memory write: {e}"

    # Durable attribution/audit record of the write request (task_04 / ADR-003):
    # who (hostname) originated the write, for which project and via which client.
    # Persisted to the write_audit_logs table so attribution is queryable and
    # survives restarts (independent of log scraping). A failure to write the
    # audit row must NOT fail the (already enqueued) write, so it is isolated.
    _record_write_audit(job_id=job_id, project=project, hostname=hostname,
                         client_name=client_name)

    logging.info(
        "write enqueued job_id=%s project=%s hostname=%s client=%s auth_method=%s auth_user=%s",
        job_id,
        project,
        hostname,
        client_name,
        auth_method_var.get() or "legacy",
        auth_user_var.get() or "-",
    )
    return json.dumps({
        "status": "accepted",
        "message": (
            "Memory received successfully. The server will process and store it "
            "in the background — no further action needed."
        ),
        "project": project,
    })



def _usage_user_id() -> str:
    """Dimensão ``user`` da atribuição de consumo (feature auth Google).

    Pessoa autenticada por token de agente (``auth_user_var``, ADR-006) quando
    presente; senão o hostname legado — comportamento byte-idêntico ao anterior
    para agentes sem token.
    """
    person = auth_user_var.get() or ""
    if auth_method_var.get() == "agent_token" and person:
        return person
    return resolve_hostname(user_id_var.get(None))


def _log_machine_divergence_if_any(hostname) -> None:
    """Loga (sem bloquear) token de agente usado em máquina não vinculada.

    Fase 1 não bloqueia divergência máquina-do-token × hostname-da-URL; o log
    estruturado é o insumo da tela de conflitos (Fase 2). Best-effort: nunca
    levanta no caminho de conexão MCP.
    """
    if auth_method_var.get() != "agent_token":
        return
    person = auth_user_var.get() or ""
    if not person or not hostname:
        return
    try:
        # Import tardio: resolve SessionLocal no momento da chamada (testável
        # via monkeypatch de app.database, como em resolve_agent_token).
        from app.database import SessionLocal as _session_factory
        from app.models import Machine, MachineStatus

        db = _session_factory()
        try:
            linked = [
                m.hostname
                for m in db.query(Machine)
                .filter(
                    Machine.linked_user_id == uuid.UUID(person),
                    Machine.status == MachineStatus.linked,
                )
                .all()
            ]
        finally:
            db.close()
        key = resolve_hostname(hostname)
        if linked and key not in linked:
            logging.warning(
                "maquina divergente: token do usuario %s usado no hostname %s "
                "(vinculadas: %s)",
                person,
                key,
                ",".join(sorted(linked)),
            )
    except Exception:  # noqa: BLE001 - verificação é best-effort
        logging.debug("verificação de divergência de máquina falhou", exc_info=True)


def _record_write_audit(*, job_id, project, hostname, client_name):
    """Persist a write-attribution audit row; never raise to the caller."""
    db = SessionLocal()
    try:
        db.add(
            WriteAuditLog(
                job_id=uuid.UUID(str(job_id)) if job_id else None,
                project=project,
                hostname=hostname,
                client_name=client_name,
                action="enqueue",
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - audit failure must not break the write
        logging.exception("could not record write audit for job_id=%s", job_id)
        db.rollback()
    finally:
        db.close()



async def _fetch_all_memories(memory_client, top_k: int = DEFAULT_LIST_TOP_K) -> list:
    """Lista memórias de toda a coleção (sem embedding) — fallback quando o embedder falha."""
    bind_active_collection(memory_client)
    raw = await anyio.to_thread.run_sync(
        lambda: memory_client.vector_store.list(filters=None, top_k=top_k)
    )
    points = raw
    if isinstance(raw, (tuple, list)) and len(raw) > 0 and isinstance(raw[0], (list, tuple)):
        points = raw[0]
    results = []
    for p in points or []:
        payload = getattr(p, "payload", {}) or {}
        results.append({
            "id": getattr(p, "id", None),
            "memory": payload.get("data"),
            "hash": payload.get("hash"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "project": payload.get("project"),
            "owner": payload.get("hostname"),
        })
    return results


@mcp.tool(description="Search stored memories across all projects, ranked by relevance and recency. The `project` parameter is a soft hint (slight boost for matching names) — wrong or slightly different project names do not exclude results. Memories are shared across all machines on the local network.")
async def search_memory(query: str, project: str, rerank: bool = False) -> str:
    # NOTE (task_03 / ADR-003): semantic reads are GLOBAL across projects and SHARED
    # across all machines. ``project`` is a ranking hint only (small boost for name
    # match); relevance + recency dominate ordering. We intentionally do NOT filter
    # by ``user_id`` (hostname is write-path attribution only).
    if not project:
        return "Error: project not provided"

    started = time.perf_counter()
    # Grupo do solicitante (ADR-003): hostname da conexão → users.group_id (Admin).
    requester_group = requester_group_for_mcp(user_id_var.get(None))
    try:
        memory_client = get_memory_client_safe()
        if not memory_client:
            return "Error: Memory system is currently unavailable. Please try again later."

        bind_active_collection(memory_client)

        filter_hash = hashlib.sha256(
            json.dumps({"mode": "global", "preferred_project": project}, sort_keys=True).encode()
        ).hexdigest()[:16]

        cached_hits = read_cache.get_search(
            project, query, DEFAULT_SEARCH_TOP_K, filter_hash
        )
        if cached_hits is not None:
            SEARCH_CACHE_HIT.inc()
            results = cached_hits
        else:
            SEARCH_CACHE_MISS.inc()
            embed_model = getattr(memory_client.embedding_model, "model", "default")
            embeddings = read_cache.get_embedding(embed_model, query)
            if embeddings is not None:
                EMBED_CACHE_HIT.inc()
            else:
                EMBED_CACHE_MISS.inc()
                try:
                    # Atribuição de tokens da embedding de busca (task_06);
                    # cache hit não consome tokens, por isso só aqui.
                    with usage_attribution(
                        project=project,
                        agent=client_name_var.get(None) or DEFAULT_CLIENT_NAME,
                        # Pessoa autenticada quando o agente usa token (ADR-006);
                        # hostname legado caso contrário.
                        user_id=_usage_user_id(),
                        operation_type="search",
                    ):
                        embeddings = await anyio.to_thread.run_sync(
                            lambda: memory_client.embedding_model.embed(query, "search")
                        )
                    read_cache.set_embedding(embed_model, query, embeddings)
                except Exception as embed_err:  # noqa: BLE001
                    logging.warning(
                        "Semantic search unavailable (%s); falling back to global list",
                        embed_err,
                    )
                    results = await _fetch_all_memories(
                        memory_client, DEFAULT_SEARCH_TOP_K
                    )
                    rank_search_results(
                        results,
                        preferred_project=project,
                        requester_group=requester_group,
                    )
                    return json.dumps(
                        {"results": results, "degraded": "list_fallback"},
                        indent=2,
                    )

            hits = await anyio.to_thread.run_sync(
                lambda: memory_client.vector_store.search(
                    query=query,
                    vectors=embeddings,
                    top_k=DEFAULT_SEARCH_TOP_K,
                    filters=None,
                    shard_key_selector=None,
                )
            )

            results = []
            for h in hits:
                id, score, payload = h.id, h.score, h.payload
                results.append({
                    "id": id,
                    "memory": payload.get("data"),
                    "hash": payload.get("hash"),
                    "created_at": payload.get("created_at"),
                    "updated_at": payload.get("updated_at"),
                    "project": payload.get("project"),
                    "owner": payload.get("hostname"),
                    "score": score,
                })
            read_cache.set_search(
                project, query, DEFAULT_SEARCH_TOP_K, filter_hash, results
            )

        # Ranqueamento aplicado APÓS o cache (group-agnóstico): solicitantes de grupos
        # diferentes compartilham o mesmo conjunto cacheado, mas recebem ordenações
        # próprias conforme o seu grupo (ADR-003).
        rank_search_results(
            results, preferred_project=project, requester_group=requester_group
        )

        return json.dumps({"results": results}, indent=2)
    except Exception as e:
        logging.exception(e)
        return f"Error searching memory: {e}"
    finally:
        SEARCH_LATENCY.observe(time.perf_counter() - started)


@mcp.tool(description="List stored memories scoped by project (shared across all machines).")
async def list_memories(project: str) -> str:
    # NOTE (task_03 / ADR-003): listing is scoped by `project` and SHARED across
    # all machines on the local network. We do NOT filter by `user_id`. The read
    # path is direct against the vector store (no write queue) and reuses the
    # memory client (no per-call reconnect).
    if not project:
        return "Error: project not provided"

    requester_group = requester_group_for_mcp(user_id_var.get(None))

    # Get memory client safely (singleton/reused; no reconnect per call)
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        # Route to the active collection (blue-green); list scans the collection
        # with the project filter (ADR-003).
        bind_active_collection(memory_client)

        # Project-only filter: shared read across hosts (no user_id restriction).
        filters = {
            "project": project,
        }

        raw = await anyio.to_thread.run_sync(
            lambda: memory_client.vector_store.list(
                filters=filters,
                top_k=DEFAULT_LIST_TOP_K,
            )
        )

        # vector_store.list may return a (points, next_page_offset) tuple or a
        # flat list depending on the backend; unwrap one level if needed.
        points = raw
        if isinstance(raw, (tuple, list)) and len(raw) > 0 and isinstance(raw[0], (list, tuple)):
            points = raw[0]

        results = []
        for p in points:
            payload = getattr(p, "payload", {}) or {}
            results.append({
                "id": getattr(p, "id", None),
                "memory": payload.get("data"),
                "hash": payload.get("hash"),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
                "project": payload.get("project"),
                "owner": payload.get("hostname"),
            })

        rank_search_results(
            results, preferred_project=project, requester_group=requester_group
        )

        return json.dumps({"results": results}, indent=2)
    except Exception as e:
        logging.exception(f"Error getting memories: {e}")
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete specific memories by their IDs")
async def delete_memories(memory_ids: list[str]) -> str:
    from app.utils.deletion_guard import check_bulk_delete_allowed, check_memory_delete_allowed

    if len(memory_ids) > 1:
        blocked = check_bulk_delete_allowed("bulk_delete")
    else:
        blocked = check_memory_delete_allowed("delete")
    if blocked:
        return f"Error: {blocked}"

    uid = resolve_hostname(user_id_var.get(None))
    client_name = client_name_var.get(None) or DEFAULT_CLIENT_NAME

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # Convert string IDs to UUIDs and filter accessible ones
            requested_ids = [uuid.UUID(mid) for mid in memory_ids]
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # Only delete memories that are both requested and accessible
            ids_to_delete = [mid for mid in requested_ids if mid in accessible_memory_ids]

            if not ids_to_delete:
                return "Error: No accessible memories found with provided IDs"

            # Delete from vector store
            for memory_id in ids_to_delete:
                try:
                    memory_client.delete(str(memory_id))
                except Exception as delete_error:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

            # Update each memory's state and create history entries
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in ids_to_delete:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                if memory:
                    # Update memory state
                    memory.state = MemoryState.deleted
                    memory.deleted_at = now

                    # Create history entry
                    history = MemoryStatusHistory(
                        memory_id=memory_id,
                        changed_by=user.id,
                        old_state=MemoryState.active,
                        new_state=MemoryState.deleted
                    )
                    db.add(history)

                    # Create access log entry
                    access_log = MemoryAccessLog(
                        memory_id=memory_id,
                        app_id=app.id,
                        access_type="delete",
                        metadata_={"operation": "delete_by_id"}
                    )
                    db.add(access_log)

            db.commit()
            return f"Successfully deleted {len(ids_to_delete)} memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    from app.utils.deletion_guard import check_bulk_delete_allowed

    blocked = check_bulk_delete_allowed("delete_all")
    if blocked:
        return f"Error: {blocked}"

    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # delete the accessible memories only
            for memory_id in accessible_memory_ids:
                try:
                    memory_client.delete(str(memory_id))
                except Exception as delete_error:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

            # Update each memory's state and create history entries
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in accessible_memory_ids:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                # Update memory state
                memory.state = MemoryState.deleted
                memory.deleted_at = now

                # Create history entry
                history = MemoryStatusHistory(
                    memory_id=memory_id,
                    changed_by=user.id,
                    old_state=MemoryState.active,
                    new_state=MemoryState.deleted
                )
                db.add(history)

                # Create access log entry
                access_log = MemoryAccessLog(
                    memory_id=memory_id,
                    app_id=app.id,
                    access_type="delete_all",
                    metadata_={"operation": "bulk_delete"}
                )
                db.add(access_log)

            db.commit()
            return "Successfully deleted all memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    """Handle SSE connections for a specific user and client"""
    # Extract user_id and client_name from path parameters
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")
    # ?group= na URL de instalação: vincula equipe na primeira conexão (ADR-004).
    ensure_user_group(uid, request.query_params.get("group"))
    # Token de agente em máquina não vinculada: log estruturado (Fase 2 trata).
    _log_machine_divergence_if_any(uid)

    try:
        # NOTE: request._send is the raw ASGI `send` callable. Starlette does not
        # expose it publicly, but the MCP SDK transports require the raw ASGI
        # interface (scope, receive, send). This is the standard pattern from the
        # MCP Python SDK examples.
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )
    finally:
        # Clean up context variables
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@mcp_router.post("/messages/")
async def handle_get_message(request: Request):
    return await _handle_post_message_impl(request)


@mcp_router.post("/{client_name}/sse/{user_id}/messages/")
async def handle_post_message(request: Request):
    return await _handle_post_message_impl(request)

async def _handle_post_message_impl(request: Request):
    """Handle POST messages for SSE"""
    try:
        body = await request.body()

        # Create a simple receive function that returns the body
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Create a simple send function that does nothing
        async def send(message):
            return {}

        # Call handle_post_message with the correct arguments
        await sse.handle_post_message(request.scope, receive, send)

        # Return a success response
        return {"status": "ok"}
    finally:
        pass


@mcp_router.api_route("/{client_name}/http/{user_id}", methods=["POST", "GET", "DELETE"])
async def handle_streamable_http(request: Request):
    """Handle Streamable HTTP connections for a specific user and client.

    Uses the Streamable HTTP transport (MCP spec 2025-03-26+) which replaces
    the deprecated SSE transport. Runs in stateless mode — each request is
    handled independently with no persistent session.

    The transport writes its response directly to the ASGI ``send`` callable.
    We intercept it via ``capture_send`` so we can return a proper ``Response``
    to FastAPI — otherwise FastAPI would also try to send its own response,
    causing a "double-response" bug.
    """
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")
    ensure_user_group(uid, request.query_params.get("group"))
    # Token de agente em máquina não vinculada: log estruturado (Fase 2 trata).
    _log_machine_divergence_if_any(uid)

    # Intercept the ASGI messages the transport sends so we can return them
    # as a single Response to FastAPI.  Without this, FastAPI would attempt to
    # write its own response after the transport already wrote one.
    response_started = False
    response_status = 200
    response_headers: list[tuple[bytes, bytes]] = []
    response_body = bytearray()

    async def capture_send(message):
        nonlocal response_started, response_status
        if message["type"] == "http.response.start":
            response_started = True
            response_status = message["status"]
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    try:
        transport = StreamableHTTPServerTransport(
            mcp_session_id=None,
            is_json_response_enabled=True,
        )

        async with anyio.create_task_group() as tg:

            async def run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
                async with transport.connect() as (read_stream, write_stream):
                    task_status.started()
                    await mcp._mcp_server.run(
                        read_stream,
                        write_stream,
                        mcp._mcp_server.create_initialization_options(),
                        stateless=True,
                    )

            await tg.start(run_server)
            await transport.handle_request(request.scope, request.receive, capture_send)
            await transport.terminate()
            tg.cancel_scope.cancel()
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)

    if not response_started:
        return Response(status_code=500, content=b"Transport did not produce a response")

    # Header dict conversion is safe here: the MCP transport in stateless JSON
    # mode only emits single-valued headers (Content-Type, Content-Length).
    return Response(
        content=bytes(response_body),
        status_code=response_status,
        headers={k.decode(): v.decode() for k, v in response_headers},
    )


def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = "mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
