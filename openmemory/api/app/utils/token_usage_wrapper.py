"""Instrumentação de consumo de tokens na camada LLM (task_02).

Por que aqui e não em ``generate_response``: os providers do mem0 retornam
apenas o conteúdo parseado (str/dict), sem o bloco ``usage`` — os contadores de
tokens só existem na resposta bruta do SDK. Este módulo envolve os métodos do
SDK subjacente do client mem0 já construído:

- LLM OpenAI-compatível: ``llm.client.chat.completions.create``
- LLM Ollama:           ``llm.client.chat``

``instrument_memory_client`` é aplicado uma única vez na construção do client
(``app.utils.memory.get_memory_client``), garantindo cobertura de qualquer
caminho (write worker, MCP server, routers) sem duplicação. Embeddings locais
não são instrumentados — só LLM entra nas métricas de consumo.

A atribuição (project/agent/user/operation) não trafega pelos kwargs do mem0;
os pontos de entrada declaram o contexto com ``usage_attribution(...)``
(contextvars — propagados por ``asyncio.to_thread``/``anyio``), e o wrapper o
lê no momento da chamada. Falha de instrumentação nunca quebra a chamada LLM.
"""

import contextvars
import functools
import logging
import time
from contextlib import contextmanager
from typing import Optional

from app.services.token_usage_service import (
    TokenUsageRecord,
    TokenUsageService,
    token_usage_service,
)

logger = logging.getLogger(__name__)

_project_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "token_usage_project", default=None
)
_agent_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "token_usage_agent", default=None
)
_user_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "token_usage_user", default=None
)
_operation_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "token_usage_operation", default=None
)

UNKNOWN = "unknown"


@contextmanager
def usage_attribution(
    *,
    project: Optional[str] = None,
    agent: Optional[str] = None,
    user_id: Optional[str] = None,
    operation_type: Optional[str] = None,
):
    """Declara a quem atribuir os tokens das chamadas LLM/embedding internas."""
    tokens = []
    for var, value in (
        (_project_var, project),
        (_agent_var, agent),
        (_user_var, user_id),
        (_operation_var, operation_type),
    ):
        if value is not None:
            tokens.append((var, var.set(value)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def current_attribution() -> dict:
    """Atribuição corrente (para o wrapper e para testes)."""
    return {
        "project": _project_var.get() or UNKNOWN,
        "agent": _agent_var.get() or UNKNOWN,
        "user_id": _user_var.get() or UNKNOWN,
        "operation_type": _operation_var.get() or UNKNOWN,
    }


# --------------------------------------------------------------------------- #
# Extração de usage por formato de resposta
# --------------------------------------------------------------------------- #
def _get(obj, key, default=None):
    """Lê ``key`` de dict ou atributo de objeto (SDKs variam)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _extract_openai_chat(response) -> dict:
    usage = _get(response, "usage")
    if usage is None:
        return {}
    prompt_details = _get(usage, "prompt_tokens_details")
    cache_read = _as_int(_get(prompt_details, "cached_tokens")) if prompt_details else 0
    return {
        "input_tokens": _as_int(_get(usage, "prompt_tokens")),
        "output_tokens": _as_int(_get(usage, "completion_tokens")),
        "total_tokens": _as_int(_get(usage, "total_tokens")),
        "cache_read_tokens": cache_read,
    }


def _extract_openai_embeddings(response) -> dict:
    usage = _get(response, "usage")
    if usage is None:
        return {}
    prompt = _as_int(_get(usage, "prompt_tokens"))
    total = _as_int(_get(usage, "total_tokens")) or prompt
    return {"input_tokens": prompt, "output_tokens": 0, "total_tokens": total}


def _extract_ollama_chat(response) -> dict:
    input_tokens = _as_int(_get(response, "prompt_eval_count"))
    output_tokens = _as_int(_get(response, "eval_count"))
    if not input_tokens and not output_tokens:
        return {}
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _extract_ollama_embed(response) -> dict:
    prompt = _as_int(_get(response, "prompt_eval_count"))
    if not prompt:
        return {}
    return {"input_tokens": prompt, "output_tokens": 0, "total_tokens": prompt}


# --------------------------------------------------------------------------- #
# Wrapper genérico
# --------------------------------------------------------------------------- #
def _current_trace_id() -> Optional[str]:
    try:
        from app.utils.tracing import current_trace_id

        return current_trace_id() or None
    except Exception:  # noqa: BLE001
        return None


def _record_call(
    service: TokenUsageService,
    *,
    usage: dict,
    model: str,
    duration_ms: int,
    default_operation: Optional[str],
    success: bool,
    error: Optional[str] = None,
) -> None:
    try:
        attribution = current_attribution()
        if default_operation and attribution["operation_type"] == UNKNOWN:
            attribution["operation_type"] = default_operation
        service.record_usage(
            TokenUsageRecord(
                **attribution,
                model=model or UNKNOWN,
                duration_ms=duration_ms,
                success=success,
                error=error,
                trace_id=_current_trace_id(),
                **usage,
            )
        )
    except Exception:  # noqa: BLE001 - métricas nunca quebram a chamada LLM
        logger.exception("token usage record failed")


def _wrap_call(orig, *, service, extractor, default_model, default_operation=None):
    @functools.wraps(orig)
    def wrapped(*args, **kwargs):
        start = time.perf_counter()
        try:
            response = orig(*args, **kwargs)
        except Exception as exc:
            _record_call(
                service,
                usage={},
                model=str(kwargs.get("model") or default_model() or UNKNOWN),
                duration_ms=int((time.perf_counter() - start) * 1000),
                default_operation=default_operation,
                success=False,
                error=str(exc),
            )
            raise
        usage = {}
        try:
            usage = extractor(response) or {}
        except Exception:  # noqa: BLE001
            logger.exception("token usage extraction failed")
        _record_call(
            service,
            usage=usage,
            model=str(kwargs.get("model") or default_model() or UNKNOWN),
            duration_ms=int((time.perf_counter() - start) * 1000),
            default_operation=default_operation,
            success=True,
        )
        return response

    wrapped.__token_usage_wrapped__ = True
    return wrapped


def _already_wrapped(fn) -> bool:
    return bool(getattr(fn, "__token_usage_wrapped__", False))


def _configured_model(provider) -> str:
    config = getattr(provider, "config", None)
    return str(getattr(config, "model", None) or UNKNOWN)


def _instrument_llm(llm, service: TokenUsageService) -> bool:
    if llm is None:
        return False
    sdk = getattr(llm, "client", None)
    if sdk is None:
        return False
    default_model = lambda: _configured_model(llm)  # noqa: E731

    # OpenAI-compatível (OpenAI, vLLM, LM Studio, APIs remotas)
    completions = getattr(getattr(sdk, "chat", None), "completions", None)
    create = getattr(completions, "create", None)
    if callable(create):
        if not _already_wrapped(create):
            completions.create = _wrap_call(
                create,
                service=service,
                extractor=_extract_openai_chat,
                default_model=default_model,
            )
        return True

    # Ollama (Client.chat é o método direto)
    chat = getattr(sdk, "chat", None)
    if callable(chat):
        if not _already_wrapped(chat):
            sdk.chat = _wrap_call(
                chat,
                service=service,
                extractor=_extract_ollama_chat,
                default_model=default_model,
            )
        return True

    logger.info(
        "token usage: LLM provider %s não suportado pela instrumentação",
        type(llm).__name__,
    )
    return False


def _instrument_embedder(embedder, service: TokenUsageService) -> bool:
    if embedder is None:
        return False
    sdk = getattr(embedder, "client", None)
    if sdk is None:
        return False
    default_model = lambda: _configured_model(embedder)  # noqa: E731

    # OpenAI-compatível
    embeddings = getattr(sdk, "embeddings", None)
    create = getattr(embeddings, "create", None)
    if callable(create):
        if not _already_wrapped(create):
            embeddings.create = _wrap_call(
                create,
                service=service,
                extractor=_extract_openai_embeddings,
                default_model=default_model,
                default_operation="embed",
            )
        return True

    # Ollama
    embed = getattr(sdk, "embed", None)
    if callable(embed):
        if not _already_wrapped(embed):
            sdk.embed = _wrap_call(
                embed,
                service=service,
                extractor=_extract_ollama_embed,
                default_model=default_model,
                default_operation="embed",
            )
        return True

    logger.info(
        "token usage: embedder %s não suportado pela instrumentação",
        type(embedder).__name__,
    )
    return False


def instrument_memory_client(client, service: Optional[TokenUsageService] = None):
    """Instrumenta apenas o LLM de um client mem0 construído. Idempotente.

    O embedder fica de fora de propósito: embeddings permanecem locais e não
  entram nas métricas de tokens (projeção de custo de API paga).

    Retorna o próprio ``client``. Nunca levanta: instrumentação é best-effort
    (providers não suportados ficam sem métricas, com log informativo).
    """
    if client is None:
        return client
    service = service or token_usage_service
    try:
        llm_ok = _instrument_llm(getattr(client, "llm", None), service)
        if llm_ok:
            logger.info("token usage instrumentation ativa (llm=%s)", llm_ok)
    except Exception:  # noqa: BLE001
        logger.exception("token usage instrumentation failed; seguindo sem métricas")
    return client
