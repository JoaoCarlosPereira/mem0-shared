"""Governance schedule configuration endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.governance_policy import get_global_policy, save_global_policy
from app.utils.governance_schedule import normalize_weekdays, parse_hhmm

router = APIRouter(prefix="/admin/governance", tags=["governance"])


class ScheduleConfigResponse(BaseModel):
    schedule_timezone: str
    schedule_weekdays: List[int]
    schedule_start_time: str
    schedule_end_time: str
    off_peak_hours_utc: List[int] = Field(
        default_factory=list,
        description="Legado — usado apenas se schedule_weekdays estiver vazio",
    )


class ScheduleConfigUpdate(BaseModel):
    schedule_timezone: str = Field(min_length=1, max_length=64)
    schedule_weekdays: List[int] = Field(min_length=1)
    schedule_start_time: str
    schedule_end_time: str

    @field_validator("schedule_weekdays")
    @classmethod
    def validate_weekdays(cls, value: List[int]) -> List[int]:
        return list(normalize_weekdays(value))

    @field_validator("schedule_start_time", "schedule_end_time")
    @classmethod
    def validate_times(cls, value: str) -> str:
        parse_hhmm(value)
        return value.strip()


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
