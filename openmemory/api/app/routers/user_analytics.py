"""Admin endpoints for user/group usage analytics dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.models import Group, User, USER_TYPE_LEGACY_HOST
from app.utils.creator_identity import (
    identity_for_hostname,
    resolve_creator_identities_with_db,
)
from app.utils.user_analytics import (
    group_activity_stats,
    recent_user_reads,
    recent_user_writes,
    user_activity_stats,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])


class GroupAnalyticsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    member_count: int
    active_members_7d: int
    writes_total: int
    writes_24h: int
    writes_7d: int
    reads_total: int
    reads_24h: int
    reads_7d: int


class UserAnalyticsSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[UUID] = None
    user_id: str
    name: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    group_id: Optional[UUID] = None
    group_name: Optional[str] = None
    created_at: Optional[datetime] = None
    writes_total: int = 0
    writes_24h: int = 0
    writes_7d: int = 0
    reads_total: int = 0
    reads_24h: int = 0
    reads_7d: int = 0
    distinct_memories_read: int = 0
    last_write_at: Optional[datetime] = None
    last_read_at: Optional[datetime] = None
    usage_level: str = "sem_atividade"


class UserAnalyticsDetail(UserAnalyticsSummary):
    writes_30d: int = 0
    reads_30d: int = 0
    distinct_projects_written: int = 0
    distinct_projects_read: int = 0
    recent_writes: list[dict] = []
    recent_reads: list[dict] = []


def _get_group_or_404(db: Session, group_id: UUID) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _user_summary(
    db: Session,
    user: User,
    *,
    identity_display_name: Optional[str] = None,
    identity_avatar_url: Optional[str] = None,
) -> UserAnalyticsSummary:
    stats = user_activity_stats(db, user.user_id)
    group_name = user.group.name if user.group else None
    return UserAnalyticsSummary(
        id=user.id,
        user_id=user.user_id,
        name=user.name,
        display_name=identity_display_name,
        avatar_url=identity_avatar_url,
        group_id=user.group_id,
        group_name=group_name,
        created_at=user.created_at,
        writes_total=stats["writes_total"],
        writes_24h=stats["writes_24h"],
        writes_7d=stats["writes_7d"],
        reads_total=stats["reads_total"],
        reads_24h=stats["reads_24h"],
        reads_7d=stats["reads_7d"],
        distinct_memories_read=stats["distinct_memories_read"],
        last_write_at=stats["last_write_at"],
        last_read_at=stats["last_read_at"],
        usage_level=stats["usage_level"],
    )


@router.get("/groups")
def list_groups_analytics(db: Session = Depends(get_db)) -> dict:
    """List all groups with aggregated usage metrics."""
    groups = db.query(Group).order_by(Group.name).all()
    items: list[dict] = []
    for group in groups:
        stats = group_activity_stats(db, group.id)
        summary = GroupAnalyticsSummary(
            id=group.id,
            name=group.name,
            member_count=stats["member_count"],
            active_members_7d=stats["active_members_7d"],
            writes_total=stats["writes_total"],
            writes_24h=stats["writes_24h"],
            writes_7d=stats["writes_7d"],
            reads_total=stats["reads_total"],
            reads_24h=stats["reads_24h"],
            reads_7d=stats["reads_7d"],
        )
        items.append(summary.model_dump(mode="json"))
    return {"groups": items}


@router.get("/groups/{group_id}")
def get_group_analytics(group_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Group detail with per-member usage stats."""
    group = _get_group_or_404(db, group_id)
    stats = group_activity_stats(db, group.id)
    members = (
        db.query(User)
        .filter(User.group_id == group_id, User.user_type == USER_TYPE_LEGACY_HOST)
        .order_by(User.user_id)
        .all()
    )
    identities = resolve_creator_identities_with_db(db, (m.user_id for m in members))
    member_summaries: list[dict] = []
    for member in members:
        identity = identity_for_hostname(member.user_id, identities)
        member_summaries.append(
            _user_summary(
                db,
                member,
                identity_display_name=(
                    identity.display_name if identity else member.display_name or member.name
                ),
                identity_avatar_url=identity.avatar_url if identity else member.avatar_url,
            ).model_dump(mode="json")
        )
    return {
        "group": GroupAnalyticsSummary(
            id=group.id,
            name=group.name,
            **stats,
        ).model_dump(mode="json"),
        "members": member_summaries,
    }


@router.get("/users/{hostname}")
def get_user_analytics(hostname: str, db: Session = Depends(get_db)) -> dict:
    """Per-user usage profile with recent write/read activity."""
    user = db.query(User).filter(User.user_id == hostname).first()
    stats = user_activity_stats(db, hostname)
    identity = identity_for_hostname(
        hostname,
        resolve_creator_identities_with_db(db, [hostname]),
    )
    if user is not None:
        summary = _user_summary(
            db,
            user,
            identity_display_name=identity.display_name if identity else None,
            identity_avatar_url=identity.avatar_url if identity else None,
        )
    else:
        summary = UserAnalyticsSummary(
            user_id=hostname,
            display_name=identity.display_name if identity else None,
            avatar_url=identity.avatar_url if identity else None,
            writes_total=stats["writes_total"],
            writes_24h=stats["writes_24h"],
            writes_7d=stats["writes_7d"],
            reads_total=stats["reads_total"],
            reads_24h=stats["reads_24h"],
            reads_7d=stats["reads_7d"],
            distinct_memories_read=stats["distinct_memories_read"],
            last_write_at=stats["last_write_at"],
            last_read_at=stats["last_read_at"],
            usage_level=stats["usage_level"],
        )
    detail = UserAnalyticsDetail(
        **summary.model_dump(),
        writes_30d=stats["writes_30d"],
        reads_30d=stats["reads_30d"],
        distinct_projects_written=stats["distinct_projects_written"],
        distinct_projects_read=stats["distinct_projects_read"],
        recent_writes=recent_user_writes(db, hostname),
        recent_reads=recent_user_reads(db, hostname),
    )
    return detail.model_dump(mode="json")


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)) -> dict:
    """Global summary for the dashboard header."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_groups = db.query(func.count(Group.id)).scalar() or 0
    groups = db.query(Group).all()
    active_users_7d = 0
    writes_total = 0
    writes_24h = 0
    writes_7d = 0
    reads_total = 0
    reads_24h = 0
    reads_7d = 0
    for group in groups:
        stats = group_activity_stats(db, group.id)
        writes_total += stats["writes_total"]
        writes_24h += stats["writes_24h"]
        writes_7d += stats["writes_7d"]
        reads_total += stats["reads_total"]
        reads_24h += stats["reads_24h"]
        reads_7d += stats["reads_7d"]
        active_users_7d += stats["active_members_7d"]
    return {
        "total_users": total_users,
        "total_groups": total_groups,
        "active_users_7d": active_users_7d,
        "writes_total": writes_total,
        "writes_24h": writes_24h,
        "writes_7d": writes_7d,
        "reads_total": reads_total,
        "reads_24h": reads_24h,
        "reads_7d": reads_7d,
    }
