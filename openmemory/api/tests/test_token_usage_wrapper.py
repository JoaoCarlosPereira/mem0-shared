"""Testes da instrumentação de tokens no nível do SDK (task_08).

Simula os quatro formatos suportados (chat OpenAI, chat Ollama, embeddings
OpenAI, embed Ollama) com SDKs fake e valida captura de usage, atribuição via
contextvars, registro de falha, idempotência e graceful degradation.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401 - resolve o ciclo models↔database (ordem de import)
from app.models import Base, TokenUsageLog
from app.services.token_usage_service import TokenUsageService
from app.utils.token_usage_wrapper import (
    current_attribution,
    instrument_memory_client,
    usage_attribution,
)


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


@pytest.fixture
def service(factory):
    svc = TokenUsageService(session_factory=factory, poll_timeout=0.05)
    yield svc
    svc.stop(timeout=2)


def _rows(factory):
    db = factory()
    try:
        return db.query(TokenUsageLog).all()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# SDKs fake
# --------------------------------------------------------------------------- #
def make_openai_llm(usage=None, exc=None):
    """LLM estilo OpenAI: client.chat.completions.create(**kwargs)."""

    class Completions:
        def create(self, **kwargs):
            if exc is not None:
                raise exc
            return SimpleNamespace(usage=usage)

    completions = Completions()
    sdk = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return SimpleNamespace(client=sdk, config=SimpleNamespace(model="gpt-test"))


def make_ollama_llm(response=None, exc=None):
    """LLM estilo Ollama: client.chat(**kwargs)."""

    def chat(**kwargs):
        if exc is not None:
            raise exc
        return response

    sdk = SimpleNamespace(chat=chat)
    return SimpleNamespace(client=sdk, config=SimpleNamespace(model="qwen3-test"))


def make_openai_embedder(usage=None):
    class Embeddings:
        def create(self, **kwargs):
            return SimpleNamespace(
                usage=usage, data=[SimpleNamespace(embedding=[0.1])]
            )

    sdk = SimpleNamespace(embeddings=Embeddings())
    return SimpleNamespace(client=sdk, config=SimpleNamespace(model="embed-test"))


def make_ollama_embedder(response=None):
    def embed(**kwargs):
        return response

    sdk = SimpleNamespace(embed=embed)
    return SimpleNamespace(client=sdk, config=SimpleNamespace(model="nomic-test"))


def make_client(llm=None, embedder=None):
    return SimpleNamespace(llm=llm, embedding_model=embedder)


# --------------------------------------------------------------------------- #
# Captura de usage por formato
# --------------------------------------------------------------------------- #
def test_openai_chat_usage_captured(service, factory):
    usage = SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=30,
        total_tokens=150,
        prompt_tokens_details=SimpleNamespace(cached_tokens=15),
    )
    client = make_client(llm=make_openai_llm(usage=usage))
    instrument_memory_client(client, service)

    client.llm.client.chat.completions.create(model="gpt-test", messages=[])
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.input_tokens == 120
    assert row.output_tokens == 30
    assert row.total_tokens == 150
    assert row.cache_read_tokens == 15
    assert row.model == "gpt-test"
    assert row.success is True
    assert row.duration_ms is not None


def test_ollama_chat_usage_captured(service, factory):
    response = {"message": {"content": "ok"}, "prompt_eval_count": 200, "eval_count": 50}
    client = make_client(llm=make_ollama_llm(response=response))
    instrument_memory_client(client, service)

    client.llm.client.chat(model="qwen3-test", messages=[])
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.input_tokens == 200
    assert row.output_tokens == 50
    assert row.total_tokens == 250
    assert row.model == "qwen3-test"


def test_openai_embeddings_usage_captured(service, factory):
    usage = SimpleNamespace(prompt_tokens=42, total_tokens=42)
    client = make_client(embedder=make_openai_embedder(usage=usage))
    instrument_memory_client(client, service)

    client.embedding_model.client.embeddings.create(model="embed-test", input=["x"])
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.input_tokens == 42
    assert row.output_tokens == 0
    assert row.total_tokens == 42
    # Sem contexto, embeddings caem no operation_type padrão "embed".
    assert row.operation_type == "embed"


def test_ollama_embed_usage_captured(service, factory):
    client = make_client(embedder=make_ollama_embedder({"prompt_eval_count": 33}))
    instrument_memory_client(client, service)

    client.embedding_model.client.embed(model="nomic-test", input="query")
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.input_tokens == 33
    assert row.total_tokens == 33


# --------------------------------------------------------------------------- #
# Atribuição, falha, idempotência
# --------------------------------------------------------------------------- #
def test_attribution_context_applied(service, factory):
    response = {"prompt_eval_count": 10, "eval_count": 5}
    client = make_client(llm=make_ollama_llm(response=response))
    instrument_memory_client(client, service)

    with usage_attribution(
        project="proj-x", agent="claude", user_id="host-9", operation_type="add"
    ):
        client.llm.client.chat(model="qwen3-test", messages=[])
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.project == "proj-x"
    assert row.agent == "claude"
    assert row.user_id == "host-9"
    assert row.operation_type == "add"


def test_attribution_resets_after_context():
    with usage_attribution(project="p", agent="a", user_id="u", operation_type="add"):
        assert current_attribution()["project"] == "p"
    assert current_attribution()["project"] == "unknown"


def test_llm_error_recorded_and_reraised(service, factory):
    client = make_client(llm=make_openai_llm(exc=RuntimeError("boom")))
    instrument_memory_client(client, service)

    with pytest.raises(RuntimeError, match="boom"):
        client.llm.client.chat.completions.create(model="gpt-test", messages=[])
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.success is False
    assert "boom" in row.error
    assert row.total_tokens == 0


def test_instrumentation_is_idempotent(service, factory):
    response = {"prompt_eval_count": 10, "eval_count": 5}
    client = make_client(llm=make_ollama_llm(response=response))
    instrument_memory_client(client, service)
    instrument_memory_client(client, service)  # segunda chamada é no-op

    client.llm.client.chat(model="qwen3-test", messages=[])
    assert service.flush(timeout=5)

    assert len(_rows(factory)) == 1


def test_unsupported_provider_is_noop(service):
    # Providers sem .client (ex.: mocks exóticos) não quebram a construção.
    client = make_client(llm=SimpleNamespace(config=SimpleNamespace(model="x")))
    assert instrument_memory_client(client, service) is client


def test_none_client_is_noop(service):
    assert instrument_memory_client(None, service) is None


def test_missing_usage_records_zero_tokens(service, factory):
    client = make_client(llm=make_openai_llm(usage=None))
    instrument_memory_client(client, service)

    client.llm.client.chat.completions.create(model="gpt-test", messages=[])
    assert service.flush(timeout=5)

    (row,) = _rows(factory)
    assert row.total_tokens == 0
    assert row.success is True


def test_metrics_db_failure_never_breaks_llm_call(factory):
    def broken_factory():
        raise RuntimeError("db down")

    svc = TokenUsageService(session_factory=broken_factory, poll_timeout=0.05)
    try:
        response = {"prompt_eval_count": 10, "eval_count": 5}
        client = make_client(llm=make_ollama_llm(response=response))
        instrument_memory_client(client, svc)

        result = client.llm.client.chat(model="qwen3-test", messages=[])
        assert result == response  # chamada LLM intacta
        svc.flush(timeout=2)
    finally:
        svc.stop(timeout=2)
