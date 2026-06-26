"""Map MCP ``Project`` rows to stable app IDs for the /api/v1/apps UI."""

from __future__ import annotations

import uuid
from typing import Any, Optional
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


def merge_app_sources(
    sql_apps: list[dict[str, Any]],
    project_apps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate legacy SQL apps and Qdrant-backed MCP projects.

    Project entries win on name collision. Empty SQL-only shells (duplicate
  ``openmemory`` rows, client names like ``claude-code`` with no SQL memories)
    are omitted from the Apps dashboard.
    """
    project_by_name = {app["name"]: app for app in project_apps}
    merged: dict[str, dict[str, Any]] = dict(project_by_name)

    for sql_app in sql_apps:
        name = sql_app["name"]
        if name in project_by_name:
            continue

        created = int(sql_app.get("total_memories_created") or 0)
        accessed = int(sql_app.get("total_memories_accessed") or 0)
        if created == 0 and accessed == 0:
            continue

        if name in merged:
            existing = merged[name]
            existing_score = int(existing.get("total_memories_created") or 0) + int(
                existing.get("total_memories_accessed") or 0
            )
            if created + accessed > existing_score:
                merged[name] = sql_app
            continue

        merged[name] = sql_app

    return list(merged.values())
