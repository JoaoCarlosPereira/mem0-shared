from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, validator

from app.utils.datetime_format import format_utc_iso


class MemoryBase(BaseModel):
    content: str
    metadata_: Optional[dict] = Field(default_factory=dict)

class MemoryCreate(MemoryBase):
    user_id: UUID
    app_id: UUID


class Category(BaseModel):
    name: str


class App(BaseModel):
    id: UUID
    name: str


class Memory(MemoryBase):
    id: UUID
    user_id: UUID
    app_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    state: str
    categories: Optional[List[Category]] = None
    app: App

    model_config = ConfigDict(from_attributes=True)

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    metadata_: Optional[dict] = None
    state: Optional[str] = None


class MemoryResponse(BaseModel):
    id: UUID
    content: str
    created_at: int
    state: str
    app_id: UUID
    app_name: str
    categories: List[str]
    metadata_: Optional[dict] = None
    # Grupo (equipe) do autor da memória, resolvido via Memory → User → Group
    # (task_09 / ADR-003). None quando o autor/grupo não é resolvível.
    group: Optional[str] = None

    @validator('created_at', pre=True)
    def convert_to_epoch(cls, v):
        if isinstance(v, datetime):
            return int(v.timestamp())
        return v

class PaginatedMemoryResponse(BaseModel):
    items: List[MemoryResponse]
    total: int
    page: int
    size: int
    pages: int


class WriteQueueJobResponse(BaseModel):
    id: str
    project: str
    hostname: str
    client_name: Optional[str]
    text_preview: str  # primeiros 120 chars do campo text
    status: str  # WriteQueueStatus enum
    error: Optional[str]
    attempts: int
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return format_utc_iso(value)


class PaginatedWriteQueueResponse(BaseModel):
    items: List[WriteQueueJobResponse]
    total: int
    page: int
    pages: int
    failed_count: int  # total de failed (sem filtro de página)


class GovernanceJobResponse(BaseModel):
    id: str
    job_type: str
    project: Optional[str]
    status: str
    attempts: int
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_utc_datetimes(self, value: datetime) -> str:
        return format_utc_iso(value)


class PaginatedGovernanceJobResponse(BaseModel):
    items: List[GovernanceJobResponse]
    total: int
    page: int
    pages: int
    failed_count: int


class WriteAuditLogResponse(BaseModel):
    id: str
    job_id: Optional[str]
    project: str
    hostname: str
    client_name: Optional[str]
    action: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return format_utc_iso(value)


class PaginatedWriteAuditResponse(BaseModel):
    items: List[WriteAuditLogResponse]
    total: int
    page: int
    pages: int


class AdminOverviewResponse(BaseModel):
    total_projects: int
    total_memories: int
    memories_last_24h: int
    write_queue_queued: int
    write_queue_processing: int
    write_queue_done: int
    write_queue_skipped: int
    write_queue_failed: int
    governance_queue_queued: int
    governance_queue_processing: int
    governance_queue_failed: int


# --------------------------------------------------------------------------- #
# Backup (task_01 / ADR-001, ADR-002, ADR-003)
# --------------------------------------------------------------------------- #
class BackupPolicySchema(BaseModel):
    """Configuração do backup autônomo, persistida em ``Config(key="backup_policy")``.

    Ver TechSpec, seção "Modelos de Dados". A validação de ``local_dir`` gravável é
    feita na camada de endpoint (PUT), pois depende do filesystem do container.
    """

    enabled: bool = False
    frequency: Literal["daily", "weekly"] = "daily"
    run_at: str = "03:00"  # HH:MM, horário off-peak
    timezone: str = "America/Sao_Paulo"  # IANA
    local_dir: str = "/mnt/backups"
    retention: int = Field(5, ge=1, le=50)
    mirror_s3: bool = False

    @field_validator("run_at")
    @classmethod
    def _valid_run_at(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("run_at deve estar no formato HH:MM")
        try:
            hh, mm = int(parts[0]), int(parts[1])
        except ValueError as exc:
            raise ValueError("run_at deve estar no formato HH:MM") from exc
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError("run_at fora do intervalo 00:00–23:59")
        return f"{hh:02d}:{mm:02d}"

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"timezone IANA inválida: {v}") from exc
        return v


class BackupArchiveInfo(BaseModel):
    name: str
    created_at: Optional[datetime] = None
    size: int = 0
    points_count: Optional[int] = None
    location: str = "local"  # local | s3


class BackupStatusResponse(BaseModel):
    last_backup: Optional[str] = None
    rpo_age_seconds: Optional[float] = None
    archives: int = 0
    last_error: Optional[str] = None


class BackupListResponse(BaseModel):
    archives: List[BackupArchiveInfo] = Field(default_factory=list)


class BackupRestoreRequest(BaseModel):
    archive: str
    confirm: str
