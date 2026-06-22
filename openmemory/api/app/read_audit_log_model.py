"""Read audit ORM model (kept separate so deploy patches can add it to models.py)."""

import uuid

from app.database import Base
from app.models import get_current_utc_time
from sqlalchemy import Column, DateTime, Index, String, UUID


class ReadAuditLog(Base):
    """Audit trail for Qdrant/MCP memory reads (search, list, get)."""

    __tablename__ = "read_audit_logs"
    id = Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    project = Column(String, nullable=False, index=True)
    memory_id = Column(String, nullable=False, index=True)
    access_type = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, index=True)
    hostname = Column(String, nullable=False, index=True)
    client_name = Column(String, nullable=True)
    query = Column(String, nullable=True)
    accessed_at = Column(DateTime, default=get_current_utc_time, index=True)

    __table_args__ = (
        Index("idx_read_audit_project_time", "project", "accessed_at"),
        Index("idx_read_audit_memory_time", "memory_id", "accessed_at"),
        Index("idx_read_audit_project_memory", "project", "memory_id"),
    )
