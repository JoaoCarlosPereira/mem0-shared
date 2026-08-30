"""Governance schedule configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.admin_auth import require_admin
from app.utils.governance_policy import (
    GOVERNANCE_PROCESS_TYPES,
    get_global_policy,
    save_global_policy,
)
from app.utils.governance_schedule import normalize_weekdays, parse_hhmm

router = APIRouter(prefix="/admin/governance", tags=["governance"])


class ScheduleConfigResponse(BaseModel):
    schedule_timezone: str
    schedule_weekdays: list[int]
    schedule_start_time: str
    schedule_end_time: str
    off_peak_hours_utc: list[int] = Field(
        default_factory=list,
        description="Legado — usado apenas se schedule_weekdays estiver vazio",
    )


class ScheduleConfigUpdate(BaseModel):
    schedule_timezone: str = Field(min_length=1, max_length=64)
    schedule_weekdays: list[int] = Field(min_length=1)
    schedule_start_time: str
    schedule_end_time: str

    @field_validator("schedule_weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        return list(normalize_weekdays(value))

    @field_validator("schedule_start_time", "schedule_end_time")
    @classmethod
    def validate_times(cls, value: str) -> str:
        parse_hhmm(value)
        return value.strip()


class ProcessesConfigResponse(BaseModel):
    processes_enabled: dict[str, bool]


class ProcessesConfigUpdate(BaseModel):
    processes_enabled: dict[str, bool]

    @field_validator("processes_enabled")
    @classmethod
    def validate_processes(cls, value: dict[str, bool]) -> dict[str, bool]:
        expected = set(GOVERNANCE_PROCESS_TYPES)
        unknown = sorted(set(value) - expected)
        missing = sorted(expected - set(value))
        if unknown:
            raise ValueError(f"processos de governança desconhecidos: {', '.join(unknown)}")
        if missing:
            raise ValueError(f"processos de governança ausentes: {', '.join(missing)}")
        return {process: bool(value[process]) for process in GOVERNANCE_PROCESS_TYPES}


def _to_response(doc: dict) -> ScheduleConfigResponse:
    weekdays = list(doc.get("schedule_weekdays") or [])
    return ScheduleConfigResponse(
        schedule_timezone=doc.get("schedule_timezone") or "UTC",
        schedule_weekdays=weekdays,
        schedule_start_time=doc.get("schedule_start_time") or "02:00",
        schedule_end_time=doc.get("schedule_end_time") or "05:00",
        off_peak_hours_utc=list(doc.get("off_peak_hours_utc") or []),
    )


@router.get("/schedule", response_model=ScheduleConfigResponse)
def get_schedule_config(db: Session = Depends(get_db)) -> ScheduleConfigResponse:
    return _to_response(get_global_policy(db))


@router.put("/schedule", response_model=ScheduleConfigResponse)
def put_schedule_config(
    body: ScheduleConfigUpdate,
    db: Session = Depends(get_db),
) -> ScheduleConfigResponse:
    try:
        global_doc = get_global_policy(db)
        updated = {
            **global_doc,
            **body.model_dump(),
        }
        saved = save_global_policy(db, updated)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_response(saved)


@router.get("/processes", response_model=ProcessesConfigResponse)
def get_processes_config(db: Session = Depends(get_db)) -> ProcessesConfigResponse:
    policy = get_global_policy(db)
    return ProcessesConfigResponse(processes_enabled=policy["processes_enabled"])


@router.put("/processes", response_model=ProcessesConfigResponse)
def put_processes_config(
    body: ProcessesConfigUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProcessesConfigResponse:
    try:
        global_doc = get_global_policy(db)
        global_doc["processes_enabled"] = body.processes_enabled
        saved = save_global_policy(db, global_doc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProcessesConfigResponse(processes_enabled=saved["processes_enabled"])
