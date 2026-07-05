"""Testes dos endpoints REST de métricas de tokens (task_08).

Exercita GET /api/v1/metrics/tokens/{summary,details,export} contra SQLite
in-memory via dependency override. O router é carregado por caminho direto
(path-load) para não puxar o __init__ pesado de app.routers.
"""

import importlib.util
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models import Base, TokenUsageLog

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "metrics.py"
_spec = importlib.util.spec_from_file_location("metrics_router_under_test", _PATH)
_metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_metrics)
router = _metrics.router


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


def make_client(factory):
    app = FastAPI()
    app.include_router(router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _log(
    *,
    project="proj-a",
    agent="claude",
    user_id="host-1",
    operation_type="add",
    model="qwen3",
    input_tokens=100,
    output_tokens=50,
    created_at=None,
    success=True,
):
    return TokenUsageLog(
        id=uuid.uuid4(),
        created_at=created_at or datetime(2026, 6, 1, 10, 0, 0),
        project=project,
        agent=agent,
        user_id=user_id,
        operation_type=operation_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cache_read_tokens=0,
        cache_write_tokens=0,
        duration_ms=800,
        success=success,
    )


@pytest.fixture
def seeded(factory):
    db = factory()
    try:
        db.add_all(
            [
                _log(created_at=datetime(2026, 6, 1, 10, 0)),
                _log(created_at=datetime(2026, 6, 1, 14, 0), input_tokens=200),
                _log(
                    created_at=datetime(2026, 6, 2, 9, 0),
                    project="proj-b",
                    agent="cursor",
                    user_id="host-2",
                    operation_type="search",
                    model="nomic",
                    input_tokens=30,
                    output_tokens=0,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()
    return factory


PARAMS = {"start": "2026-06-01T00:00:00", "end": "2026-06-30T00:00:00"}


# --------------------------------------------------------------------------- #
# /tokens/summary
# --------------------------------------------------------------------------- #
def test_summary_by_project(seeded):
    client = make_client(seeded)
    r = client.get("/api/v1/metrics/tokens/summary", params=PARAMS)
    assert r.status_code == 200
    body = r.json()
    assert body["granularity"] == "project"
    rows = {(row["period"], row["group"]): row for row in body["data"]}
    assert rows[("2026-06-01", "proj-a")]["input_tokens"] == 300
    assert rows[("2026-06-01", "proj-a")]["output_tokens"] == 100
    assert rows[("2026-06-01", "proj-a")]["total_tokens"] == 400
    assert rows[("2026-06-01", "proj-a")]["operation_count"] == 2
    assert rows[("2026-06-01", "proj-a")]["avg_tokens_per_op"] == 200
    assert ("2026-06-02", "proj-b") not in rows


@pytest.mark.parametrize(
    "granularity,expected_groups",
    [
        ("agent", {"claude"}),
        ("user", {"host-1"}),
        ("model", {"qwen3"}),
    ],
)
def test_summary_granularities(seeded, granularity, expected_groups):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/summary",
        params={**PARAMS, "granularity": granularity},
    )
    assert r.status_code == 200
    assert {row["group"] for row in r.json()["data"]} == expected_groups


def test_summary_filter_by_project(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/summary", params={**PARAMS, "project": "proj-b"}
    )
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_summary_excludes_embedding_rows(seeded):
    client = make_client(seeded)
    r = client.get("/api/v1/metrics/tokens/summary", params=PARAMS)
    groups = {row["group"] for row in r.json()["data"]}
    assert "proj-b" not in groups


def test_summary_filter_by_operation_type(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/summary",
        params={**PARAMS, "operation_type": ["search"]},
    )
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_summary_invalid_start_returns_422(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/summary", params={"start": "invalid-date"}
    )
    assert r.status_code == 422


def test_summary_invalid_granularity_returns_422(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/summary",
        params={**PARAMS, "granularity": "invalid"},
    )
    assert r.status_code == 422


def test_summary_missing_start_returns_422(seeded):
    client = make_client(seeded)
    r = client.get("/api/v1/metrics/tokens/summary")
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# /tokens/details
# --------------------------------------------------------------------------- #
def test_details_pagination(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/details",
        params={**PARAMS, "page": 1, "page_size": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["data"]) == 2

    r2 = client.get(
        "/api/v1/metrics/tokens/details",
        params={**PARAMS, "page": 2, "page_size": 2},
    )
    assert len(r2.json()["data"]) == 0


def test_details_sorting_by_total_tokens_desc(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/details",
        params={**PARAMS, "sort_by": "total_tokens", "sort_order": "desc"},
    )
    totals = [row["total_tokens"] for row in r.json()["data"]]
    assert totals == sorted(totals, reverse=True)


def test_details_row_shape(seeded):
    client = make_client(seeded)
    r = client.get("/api/v1/metrics/tokens/details", params=PARAMS)
    row = r.json()["data"][0]
    for field in (
        "id",
        "created_at",
        "project",
        "agent",
        "user_id",
        "operation_type",
        "model",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "duration_ms",
        "success",
    ):
        assert field in row


def test_details_invalid_page_size_returns_422(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/details", params={**PARAMS, "page_size": 9999}
    )
    assert r.status_code == 422


def test_details_invalid_sort_by_returns_422(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/details", params={**PARAMS, "sort_by": "hacker"}
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------- #
# /tokens/export
# --------------------------------------------------------------------------- #
def test_export_returns_csv_with_all_rows(seeded):
    client = make_client(seeded)
    r = client.get("/api/v1/metrics/tokens/export", params=PARAMS)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]

    lines = [line for line in r.text.strip().splitlines() if line]
    assert lines[0].split(",") == _metrics.EXPORT_COLUMNS
    assert len(lines) == 1 + 2  # header + 2 registros LLM


def test_export_respects_filters(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/export", params={**PARAMS, "project": "proj-b"}
    )
    lines = [line for line in r.text.strip().splitlines() if line]
    assert len(lines) == 1  # só header — embed de proj-b excluído


def test_export_period_filter_excludes_out_of_range(seeded):
    client = make_client(seeded)
    r = client.get(
        "/api/v1/metrics/tokens/export",
        params={"start": "2026-06-02T00:00:00", "end": "2026-06-30T00:00:00"},
    )
    lines = [line for line in r.text.strip().splitlines() if line]
    assert len(lines) == 1 + 1  # único LLM em 2026-06-02 seria embed — nenhum
