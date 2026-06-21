from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, validator


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
    write_queue_failed: int
    governance_queue_queued: int
    governance_queue_processing: int
    governance_queue_failed: int
