"""Map MCP ``Project`` rows to stable app IDs for the /api/v1/apps UI."""

from __future__ import annotations

import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Project

# Stable namespace so project cards keep the same UUID across restarts.
PROJECT_APP_NAMESPACE = uuid.UUID("0192e8c4-0000-7000-8000-000000000001")


def project_to_app_id(project_name: str) -> UUID:
    return uuid.uuid5(PROJECT_APP_NAMESPACE, f"openmemory-project:{project_name}")


def resolve_project_name(db: Session, app_id: UUID) -> Optional[str]:
    for project in db.query(Project).all():
        if project_to_app_id(project.name) == app_id:
            return project.name
    return None
