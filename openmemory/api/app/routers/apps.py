from typing import Any, Optional
from uuid import UUID

from app.database import get_db
from app.models import App, Memory, MemoryAccessLog, MemoryState, Project
from app.utils.project_apps import project_to_app_id, resolve_project_name
from app.utils.read_audit import (
    count_distinct_memories_accessed,
    list_project_accessed_memories,
    project_access_stats,
)
from app.utils.vector_stats import count_project_memories, list_shared_memories
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/api/v1/apps", tags=["apps"])


def get_app_or_404(db: Session, app_id: UUID) -> App:
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app


def _sql_apps(db: Session, name: Optional[str], is_active: Optional[bool]) -> list[dict[str, Any]]:
    memory_counts = (
        db.query(
            Memory.app_id,
            func.count(Memory.id).label("memory_count"),
        )
        .filter(Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived]))
        .group_by(Memory.app_id)
        .subquery()
    )
    access_counts = (
        db.query(
            MemoryAccessLog.app_id,
            func.count(func.distinct(MemoryAccessLog.memory_id)).label("access_count"),
        )
        .group_by(MemoryAccessLog.app_id)
        .subquery()
    )

    query = (
        db.query(
            App,
            func.coalesce(memory_counts.c.memory_count, 0).label("total_memories_created"),
            func.coalesce(access_counts.c.access_count, 0).label("total_memories_accessed"),
        )
        .outerjoin(memory_counts, App.id == memory_counts.c.app_id)
        .outerjoin(access_counts, App.id == access_counts.c.app_id)
    )

    if name:
        query = query.filter(App.name.ilike(f"%{name}%"))
    if is_active is not None:
        query = query.filter(App.is_active == is_active)

    rows = query.all()
    return [
        {
            "id": row[0].id,
            "name": row[0].name,
            "is_active": row[0].is_active,
            "total_memories_created": row[1],
            "total_memories_accessed": row[2],
            "source": "sql",
        }
        for row in rows
    ]


def _project_apps(db: Session, name: Optional[str], is_active: Optional[bool]) -> list[dict[str, Any]]:
    if is_active is False:
        return []

    apps: list[dict[str, Any]] = []
    for project in db.query(Project).order_by(Project.name).all():
        if name and name.lower() not in project.name.lower():
            continue
        accessed = count_distinct_memories_accessed(db, project.name)
        apps.append(
            {
                "id": project_to_app_id(project.name),
                "name": project.name,
                "is_active": True,
                "total_memories_created": count_project_memories(project.name),
                "total_memories_accessed": accessed,
                "source": "project",
            }
        )
    return apps


def _sort_apps(apps: list[dict[str, Any]], sort_by: str, sort_direction: str) -> list[dict[str, Any]]:
    reverse = sort_direction.lower() == "desc"
    if sort_by == "memories":
        key = lambda a: a["total_memories_created"]  # noqa: E731
    elif sort_by == "memories_accessed":
        key = lambda a: a["total_memories_accessed"]  # noqa: E731
    else:
        key = lambda a: a["name"].lower()  # noqa: E731
    return sorted(apps, key=key, reverse=reverse)


@router.get("/")
async def list_apps(
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = "name",
    sort_direction: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List SQL apps plus MCP projects (Qdrant-backed) for the Apps dashboard."""
    merged = _sql_apps(db, name, is_active) + _project_apps(db, name, is_active)
    merged = _sort_apps(merged, sort_by, sort_direction)

    total = len(merged)
    start = (page - 1) * page_size
    page_items = merged[start : start + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "apps": [
            {
                "id": app["id"],
                "name": app["name"],
                "is_active": app["is_active"],
                "total_memories_created": app["total_memories_created"],
                "total_memories_accessed": app["total_memories_accessed"],
            }
            for app in page_items
        ],
    }


@router.get("/{app_id}")
async def get_app_details(
    app_id: UUID,
    db: Session = Depends(get_db),
):
    project_name = resolve_project_name(db, app_id)
    if project_name:
        count = count_project_memories(project_name)
        accessed, first_accessed, last_accessed = project_access_stats(db, project_name)
        return {
            "is_active": True,
            "total_memories_created": count,
            "total_memories_accessed": accessed,
            "first_accessed": first_accessed,
            "last_accessed": last_accessed,
        }

    app = get_app_or_404(db, app_id)
    access_stats = (
        db.query(
            func.count(MemoryAccessLog.id).label("total_memories_accessed"),
            func.min(MemoryAccessLog.accessed_at).label("first_accessed"),
            func.max(MemoryAccessLog.accessed_at).label("last_accessed"),
        )
        .filter(MemoryAccessLog.app_id == app_id)
        .first()
    )

    return {
        "is_active": app.is_active,
        "total_memories_created": db.query(Memory).filter(Memory.app_id == app_id).count(),
        "total_memories_accessed": access_stats.total_memories_accessed or 0,
        "first_accessed": access_stats.first_accessed,
        "last_accessed": access_stats.last_accessed,
    }


@router.get("/{app_id}/memories")
async def list_app_memories(
    app_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    project_name = resolve_project_name(db, app_id)
    if project_name:
        data = list_shared_memories(project=project_name, page=page, size=page_size)
        return {
            "total": data["total"],
            "page": data["page"],
            "page_size": data["size"],
            "memories": [
                {
                    "id": item["id"],
                    "content": item["content"],
                    "created_at": item["created_at"],
                    "state": item["state"],
                    "app_id": str(app_id),
                    "app_name": item["app_name"],
                    "categories": item["categories"],
                    "metadata_": item.get("metadata_"),
                }
                for item in data["items"]
            ],
        }

    get_app_or_404(db, app_id)
    query = db.query(Memory).filter(
        Memory.app_id == app_id,
        Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived]),
    )
    query = query.options(joinedload(Memory.categories))
    total = query.count()
    memories = (
        query.order_by(Memory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "id": memory.id,
                "content": memory.content,
                "created_at": memory.created_at,
                "state": memory.state.value,
                "app_id": memory.app_id,
                "app_name": memory.app.name if memory.app else None,
                "categories": [category.name for category in memory.categories],
                "metadata_": memory.metadata_,
            }
            for memory in memories
        ],
    }


@router.get("/{app_id}/accessed")
async def list_app_accessed_memories(
    app_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    project_name = resolve_project_name(db, app_id)
    if project_name:
        total, memories = list_project_accessed_memories(
            db, project_name, page=page, page_size=page_size
        )
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "memories": memories,
        }

    query = (
        db.query(
            Memory,
            func.count(MemoryAccessLog.id).label("access_count"),
        )
        .join(MemoryAccessLog, Memory.id == MemoryAccessLog.memory_id)
        .filter(MemoryAccessLog.app_id == app_id)
        .group_by(Memory.id)
        .order_by(desc("access_count"))
    )
    query = query.options(joinedload(Memory.categories))

    total = query.count()
    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "memory": {
                    "id": memory.id,
                    "content": memory.content,
                    "created_at": memory.created_at,
                    "state": memory.state.value,
                    "app_id": memory.app_id,
                    "app_name": memory.app.name if memory.app else None,
                    "categories": [category.name for category in memory.categories],
                    "metadata_": memory.metadata_,
                },
                "access_count": count,
            }
            for memory, count in results
        ],
    }


@router.put("/{app_id}")
async def update_app_details(
    app_id: UUID,
    is_active: bool,
    db: Session = Depends(get_db),
):
    if resolve_project_name(db, app_id):
        return {"status": "success", "message": "MCP projects are always active"}

    app = get_app_or_404(db, app_id)
    app.is_active = is_active
    db.commit()
    return {"status": "success", "message": "Updated app details successfully"}
