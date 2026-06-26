from app.database import get_db
from app.models import App, Memory, MemoryState, Project, User
from app.utils.vector_stats import count_collection_memories
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/")
async def get_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sql_memories = (
        db.query(Memory)
        .filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted)
        .count()
    )
    # MCP writes live in Qdrant; surface the larger of SQL catalog vs vector store.
    total_memories = max(sql_memories, count_collection_memories())

    apps = db.query(App).filter(App.owner_id == user.id)
    project_count = db.query(Project).count()
    total_apps = max(apps.count(), project_count)

    return {
        "total_memories": total_memories,
        "total_apps": total_apps,
        "apps": [
            {
                "id": str(app.id),
                "name": app.name,
                "description": app.description,
                "is_active": app.is_active,
                "created_at": app.created_at,
                "updated_at": app.updated_at,
            }
            for app in apps.all()
        ],
    }
