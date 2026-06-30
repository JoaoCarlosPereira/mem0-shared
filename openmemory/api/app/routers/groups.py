"""Admin endpoints para gestão de grupos de usuários (task_06 / ADR-002).

CRUD de grupos e gestão de membros sob ``/admin/groups``. Fica sob o
``TeamAuthMiddleware`` global, como as demais telas admin (sem proteção adicional no
MVP). Operações de membro atualizam ``users.group_id`` e invalidam o cache de grupo
usado no ranqueamento (ADR-003).

Regras:
- nome de grupo único (case-insensitive); duplicado => 409;
- remover grupo com membros => 400; remover o grupo Default => 403;
- remover um membro o realoca para o grupo Default.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from app.database import get_db
from app.models import DEFAULT_GROUP_NAME, Group, User
from app.utils.groups import (
    get_or_create_group,
    invalidate_group_cache,
    normalize_group_name,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/groups", tags=["groups"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class GroupCreate(BaseModel):
    name: str


class GroupUpdate(BaseModel):
    name: str


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    member_count: int = 0


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: str
    name: Optional[str] = None


class MemberAdd(BaseModel):
    user_id: str  # hostname (User.user_id)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_group_or_404(db: Session, group_id: UUID) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _is_default(group: Group) -> bool:
    return group.name.lower() == DEFAULT_GROUP_NAME.lower()


def _name_taken(db: Session, name: str, exclude_id: Optional[UUID] = None) -> bool:
    q = db.query(Group).filter(func.lower(Group.name) == name.lower())
    if exclude_id is not None:
        q = q.filter(Group.id != exclude_id)
    return db.query(q.exists()).scalar()


# --------------------------------------------------------------------------- #
# Grupos
# --------------------------------------------------------------------------- #
@router.get("")
def list_groups(db: Session = Depends(get_db)) -> dict:
    """Lista grupos com a contagem de membros."""
    rows = (
        db.query(Group, func.count(User.id))
        .outerjoin(User, User.group_id == Group.id)
        .group_by(Group.id)
        .order_by(Group.name)
        .all()
    )
    groups = [
        GroupResponse(id=g.id, name=g.name, member_count=count) for g, count in rows
    ]
    return {"groups": [g.model_dump() for g in groups]}


@router.post("", status_code=201)
def create_group(payload: GroupCreate, db: Session = Depends(get_db)) -> dict:
    name = normalize_group_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Group name must not be empty")
    if _name_taken(db, name):
        raise HTTPException(status_code=409, detail="Group name already exists")
    group = Group(name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return GroupResponse(id=group.id, name=group.name, member_count=0).model_dump()


@router.put("/{group_id}")
def update_group(group_id: UUID, payload: GroupUpdate, db: Session = Depends(get_db)) -> dict:
    group = _get_group_or_404(db, group_id)
    name = normalize_group_name(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Group name must not be empty")
    if _name_taken(db, name, exclude_id=group_id):
        raise HTTPException(status_code=409, detail="Group name already exists")
    group.name = name
    db.commit()
    db.refresh(group)
    count = db.query(func.count(User.id)).filter(User.group_id == group.id).scalar()
    return GroupResponse(id=group.id, name=group.name, member_count=count).model_dump()


@router.delete("/{group_id}")
def delete_group(group_id: UUID, db: Session = Depends(get_db)) -> dict:
    group = _get_group_or_404(db, group_id)
    if _is_default(group):
        raise HTTPException(status_code=403, detail="The Default group cannot be removed")
    member_count = db.query(func.count(User.id)).filter(User.group_id == group.id).scalar()
    if member_count:
        raise HTTPException(
            status_code=400,
            detail="Group still has members; reassign them before deleting",
        )
    db.delete(group)
    db.commit()
    return {"status": "deleted"}


# --------------------------------------------------------------------------- #
# Membros
# --------------------------------------------------------------------------- #
@router.get("/{group_id}/members")
def list_members(group_id: UUID, db: Session = Depends(get_db)) -> dict:
    _get_group_or_404(db, group_id)
    members = db.query(User).filter(User.group_id == group_id).order_by(User.user_id).all()
    return {"members": [MemberResponse.model_validate(m).model_dump() for m in members]}


@router.post("/{group_id}/members")
def add_member(group_id: UUID, payload: MemberAdd, db: Session = Depends(get_db)) -> dict:
    group = _get_group_or_404(db, group_id)
    user = db.query(User).filter(User.user_id == payload.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.group_id = group.id
    db.commit()
    invalidate_group_cache(user.user_id)
    return MemberResponse.model_validate(user).model_dump()


@router.delete("/{group_id}/members/{user_id}")
def remove_member(group_id: UUID, user_id: str, db: Session = Depends(get_db)) -> dict:
    _get_group_or_404(db, group_id)
    user = (
        db.query(User)
        .filter(User.user_id == user_id, User.group_id == group_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Member not found in this group")
    # Realoca para o grupo Default (mantém a invariante "todo usuário tem um grupo").
    default_group = get_or_create_group(db, DEFAULT_GROUP_NAME)
    user.group_id = default_group.id
    db.commit()
    invalidate_group_cache(user.user_id)
    return {"status": "moved_to_default"}
