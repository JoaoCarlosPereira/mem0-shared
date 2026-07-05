"""Endpoints REST de métricas de consumo de tokens LLM (task_03).

Três endpoints sob ``/api/v1/metrics/tokens``:

- ``GET /summary``: agregação por período (dia) + dimensão (project/agent/
  user/model) para gráficos de tendência.
- ``GET /details``: linhas individuais com paginação e ordenação dinâmica.
- ``GET /export``: CSV com todas as colunas, mesmos filtros (sem paginação).

Somente chamadas de **chat LLM** entram nos totais (``output_tokens > 0``).
Embeddings locais são excluídos — histórico antigo de embed também some dos
agregados.

O bucket de período usa expressão por dialeto (``to_char`` no PostgreSQL,
``strftime`` no SQLite) porque ``date_trunc`` não existe no SQLite usado em
testes e no deploy local-first.
"""

import csv
import io
from datetime import datetime, timezone
from typing import List, Literal, Optional

from app.database import get_db, is_postgresql
from app.models import TokenUsageLog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

Granularity = Literal["project", "agent", "user", "model"]
SortBy = Literal[
    "created_at", "total_tokens", "input_tokens", "output_tokens", "duration_ms"
]
SortOrder = Literal["asc", "desc"]

MAX_PAGE_SIZE = 500
EXPORT_CHUNK = 500

_GROUP_COLUMNS = {
    "project": TokenUsageLog.project,
    "agent": TokenUsageLog.agent,
    "user": TokenUsageLog.user_id,
    "model": TokenUsageLog.model,
}

_SORT_COLUMNS = {
    "created_at": TokenUsageLog.created_at,
    "total_tokens": TokenUsageLog.total_tokens,
    "input_tokens": TokenUsageLog.input_tokens,
    "output_tokens": TokenUsageLog.output_tokens,
    "duration_ms": TokenUsageLog.duration_ms,
}

EXPORT_COLUMNS = [
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
    "cache_read_tokens",
    "cache_write_tokens",
    "duration_ms",
    "success",
    "error",
    "trace_id",
]


class TokenSummaryRow(BaseModel):
    period: str
    group: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    operation_count: int
    avg_tokens_per_op: int


class TokenSummaryResponse(BaseModel):
    granularity: Granularity
    data: List[TokenSummaryRow]


class TokenUsageDetail(BaseModel):
    id: str
    created_at: Optional[datetime]
    project: str
    agent: str
    user_id: str
    operation_type: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    duration_ms: Optional[int]
    success: bool
    error: Optional[str]
    trace_id: Optional[str]


class TokenDetailsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: List[TokenUsageDetail]


def _period_expr():
    if is_postgresql():
        return func.to_char(TokenUsageLog.created_at, "YYYY-MM-DD")
    return func.strftime("%Y-%m-%d", TokenUsageLog.created_at)


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normaliza datas aware para UTC naive (padrão de created_at no banco)."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _llm_only_filter(query):
    """Exclui embeddings (sem completion tokens) dos agregados de consumo."""
    return query.filter(TokenUsageLog.output_tokens > 0)


def _apply_filters(
    query,
    *,
    start: Optional[datetime],
    end: Optional[datetime],
    operation_type: Optional[List[str]],
    project: Optional[str],
    agent: Optional[str],
    user_id: Optional[str],
    model: Optional[str],
):
    query = _llm_only_filter(query)
    start = _naive_utc(start)
    end = _naive_utc(end)
    if start is not None:
        query = query.filter(TokenUsageLog.created_at >= start)
    if end is not None:
        query = query.filter(TokenUsageLog.created_at < end)
    if operation_type:
        query = query.filter(TokenUsageLog.operation_type.in_(operation_type))
    if project:
        query = query.filter(TokenUsageLog.project == project)
    if agent:
        query = query.filter(TokenUsageLog.agent == agent)
    if user_id:
        query = query.filter(TokenUsageLog.user_id == user_id)
    if model:
        query = query.filter(TokenUsageLog.model == model)
    return query


@router.get("/tokens/summary", response_model=TokenSummaryResponse)
async def tokens_summary(
    start: datetime = Query(..., description="Data inicial (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="Data final (padrão: agora)"),
    granularity: Granularity = Query("project"),
    operation_type: Optional[List[str]] = Query(None),
    project: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Agrega tokens por dia + dimensão selecionada para os gráficos da UI."""
    group_col = _GROUP_COLUMNS[granularity]
    period = _period_expr().label("period")
    query = db.query(
        period,
        group_col.label("group"),
        func.coalesce(func.sum(TokenUsageLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(TokenUsageLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("total_tokens"),
        func.count(TokenUsageLog.id).label("operation_count"),
    )
    query = _apply_filters(
        query,
        start=start,
        end=end,
        operation_type=operation_type,
        project=project,
        agent=agent,
        user_id=user_id,
        model=model,
    )
    rows = query.group_by("period", group_col).order_by(asc("period")).all()

    data = [
        TokenSummaryRow(
            period=row.period,
            group=row.group,
            input_tokens=int(row.input_tokens),
            output_tokens=int(row.output_tokens),
            total_tokens=int(row.total_tokens),
            operation_count=int(row.operation_count),
            avg_tokens_per_op=(
                round(row.total_tokens / row.operation_count)
                if row.operation_count
                else 0
            ),
        )
        for row in rows
    ]
    return TokenSummaryResponse(granularity=granularity, data=data)


def _details_query(
    db: Session,
    *,
    start: Optional[datetime],
    end: Optional[datetime],
    operation_type: Optional[List[str]],
    project: Optional[str],
    agent: Optional[str],
    user_id: Optional[str],
    model: Optional[str],
    sort_by: str,
    sort_order: str,
):
    query = _apply_filters(
        db.query(TokenUsageLog),
        start=start,
        end=end,
        operation_type=operation_type,
        project=project,
        agent=agent,
        user_id=user_id,
        model=model,
    )
    order = asc if sort_order == "asc" else desc
    return query.order_by(order(_SORT_COLUMNS[sort_by]))


def _detail_from_row(row: TokenUsageLog) -> TokenUsageDetail:
    return TokenUsageDetail(
        id=str(row.id),
        created_at=row.created_at,
        project=row.project,
        agent=row.agent,
        user_id=row.user_id,
        operation_type=row.operation_type,
        model=row.model,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        cache_read_tokens=row.cache_read_tokens,
        cache_write_tokens=row.cache_write_tokens,
        duration_ms=row.duration_ms,
        success=row.success,
        error=row.error,
        trace_id=row.trace_id,
    )


@router.get("/tokens/details", response_model=TokenDetailsResponse)
async def tokens_details(
    start: datetime = Query(..., description="Data inicial (ISO 8601)"),
    end: Optional[datetime] = Query(None),
    operation_type: Optional[List[str]] = Query(None),
    project: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    sort_by: SortBy = Query("created_at"),
    sort_order: SortOrder = Query("desc"),
    db: Session = Depends(get_db),
):
    """Linhas individuais de consumo com paginação e ordenação."""
    query = _details_query(
        db,
        start=start,
        end=end,
        operation_type=operation_type,
        project=project,
        agent=agent,
        user_id=user_id,
        model=model,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return TokenDetailsResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=[_detail_from_row(row) for row in rows],
    )


@router.get("/tokens/export")
async def tokens_export(
    start: datetime = Query(..., description="Data inicial (ISO 8601)"),
    end: Optional[datetime] = Query(None),
    operation_type: Optional[List[str]] = Query(None),
    project: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    sort_by: SortBy = Query("created_at"),
    sort_order: SortOrder = Query("desc"),
    db: Session = Depends(get_db),
):
    """Exporta as linhas filtradas em CSV (todas as colunas, sem paginação)."""
    query = _details_query(
        db,
        start=start,
        end=end,
        operation_type=operation_type,
        project=project,
        agent=agent,
        user_id=user_id,
        model=model,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    def _iter_csv():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(EXPORT_COLUMNS)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        for row in query.yield_per(EXPORT_CHUNK):
            writer.writerow(
                [
                    str(row.id),
                    row.created_at.isoformat() if row.created_at else "",
                    row.project,
                    row.agent,
                    row.user_id,
                    row.operation_type,
                    row.model,
                    row.input_tokens,
                    row.output_tokens,
                    row.total_tokens,
                    row.cache_read_tokens,
                    row.cache_write_tokens,
                    row.duration_ms if row.duration_ms is not None else "",
                    row.success,
                    row.error or "",
                    row.trace_id or "",
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"token-usage-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
