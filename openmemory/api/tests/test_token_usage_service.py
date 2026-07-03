"""Testes do TokenUsageService (task_08 / PRD metricas-consumo-recursos).

Valida a persistência assíncrona (fila + thread de flush), defaults do
schema, gravação em lote e a degradação graciosa quando o banco falha.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database  # noqa: F401 - resolve o ciclo models↔database (ordem de import)
from app.models import Base, TokenUsageLog
from app.services.token_usage_service import TokenUsageRecord, TokenUsageService


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


def _record(**overrides):
    base = dict(
        project="proj-a",
        agent="claude",
        user_id="host-1",
        operation_type="add",
        model="qwen3",
        input_tokens=100,
        output_tokens=40,
        total_tokens=140,
        duration_ms=850,
    )
    base.update(overrides)
    return TokenUsageRecord(**base)


def test_record_usage_persists_complete_row(service, factory):
    service.record_usage(_record(cache_read_tokens=10, trace_id="abc123"))
    assert service.flush(timeout=5)

    db = factory()
    try:
        rows = db.query(TokenUsageLog).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.project == "proj-a"
        assert row.agent == "claude"
        assert row.user_id == "host-1"
        assert row.operation_type == "add"
        assert row.model == "qwen3"
        assert row.input_tokens == 100
        assert row.output_tokens == 40
        assert row.total_tokens == 140
        assert row.cache_read_tokens == 10
        assert row.cache_write_tokens == 0
        assert row.duration_ms == 850
        assert row.success is True
        assert row.error is None
        assert row.trace_id == "abc123"
        assert row.created_at is not None
    finally:
        db.close()


def test_record_usage_minimal_defaults(service, factory):
    service.record_usage(TokenUsageRecord())
    assert service.flush(timeout=5)

    db = factory()
    try:
        row = db.query(TokenUsageLog).one()
        assert row.project == "unknown"
        assert row.agent == "unknown"
        assert row.user_id == "unknown"
        assert row.operation_type == "unknown"
        assert row.model == "unknown"
        assert row.input_tokens == 0
        assert row.cache_read_tokens == 0
        assert row.success is True
        assert row.duration_ms is None
    finally:
        db.close()


def test_record_usage_failure_row(service, factory):
    service.record_usage(
        _record(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            success=False,
            error="connection refused",
        )
    )
    assert service.flush(timeout=5)

    db = factory()
    try:
        row = db.query(TokenUsageLog).one()
        assert row.success is False
        assert row.error == "connection refused"
        assert row.total_tokens == 0
    finally:
        db.close()


def test_record_many_batches_in_one_flush(service, factory):
    service.record_many([_record(input_tokens=i) for i in range(5)])
    assert service.flush(timeout=5)

    db = factory()
    try:
        assert db.query(TokenUsageLog).count() == 5
    finally:
        db.close()


def test_db_failure_is_swallowed():
    def broken_factory():
        raise RuntimeError("db down")

    svc = TokenUsageService(session_factory=broken_factory, poll_timeout=0.05)
    try:
        # Nunca deve propagar: o caminho LLM não pode quebrar por métricas.
        svc.record_usage(_record())
        assert svc.flush(timeout=5)
    finally:
        svc.stop(timeout=2)


def test_writer_recovers_after_transient_failure(factory):
    calls = {"n": 0}

    def flaky_factory():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return factory()

    svc = TokenUsageService(session_factory=flaky_factory, poll_timeout=0.05)
    try:
        svc.record_usage(_record())
        assert svc.flush(timeout=5)  # primeiro lote é perdido, loop sobrevive
        svc.record_usage(_record())
        assert svc.flush(timeout=5)

        db = factory()
        try:
            assert db.query(TokenUsageLog).count() == 1
        finally:
            db.close()
    finally:
        svc.stop(timeout=2)
