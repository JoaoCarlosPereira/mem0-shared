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
from app.models import DEFAULT_GROUP_NAME, Group, Machine, User, USER_TYPE_LEGACY_HOST
from app.utils.machine_resolver import consolidate_legacy_host_users, find_legacy_host_user
from app.utils.creator_identity import identity_for_hostname, resolve_creator_identities_with_db
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
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


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


def _legacy_members_query(db: Session, group_id: UUID):
    """Membros de grupo são hostnames (``legacy_host``), não contas Google ``person``."""
    return db.query(User).filter(
        User.group_id == group_id,
        User.user_type == USER_TYPE_LEGACY_HOST,
    )


def _legacy_member_count(db: Session, group_id: UUID) -> int:
    return _legacy_members_query(db, group_id).count()


def _member_response(db: Session, user: User) -> dict:
    identities = resolve_creator_identities_with_db(db, [user.user_id])
    identity = identity_for_hostname(user.user_id, identities)
    return MemberResponse(
        id=user.id,
        user_id=user.user_id,
        name=user.name,
        display_name=identity.display_name if identity else user.display_name or user.name,
        avatar_url=identity.avatar_url if identity else user.avatar_url,
    ).model_dump()


def _sync_linked_person_group(db: Session, legacy_user: User, group_id: UUID) -> None:
    """Mantém ``person.group_id`` alinhado ao hostname legado (ADR-004/005)."""
    machine = (
        db.query(Machine)
        .filter(Machine.legacy_user_id == legacy_user.id, Machine.linked_user_id.isnot(None))
        .first()
    )
    if machine is None:
        return
    person = db.query(User).filter(User.id == machine.linked_user_id).first()
    if person is not None:
        person.group_id = group_id


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
        .outerjoin(
            User,
            (User.group_id == Group.id) & (User.user_type == USER_TYPE_LEGACY_HOST),
        )
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
    count = _legacy_member_count(db, group.id)
    return GroupResponse(id=group.id, name=group.name, member_count=count).model_dump()


@router.delete("/{group_id}")
def delete_group(group_id: UUID, db: Session = Depends(get_db)) -> dict:
    group = _get_group_or_404(db, group_id)
    if _is_default(group):
        raise HTTPException(status_code=403, detail="The Default group cannot be removed")
    member_count = _legacy_member_count(db, group.id)
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
    members = _legacy_members_query(db, group_id).order_by(User.user_id).all()
    identities = resolve_creator_identities_with_db(db, (m.user_id for m in members))
    items: list[dict] = []
    for member in members:
        identity = identity_for_hostname(member.user_id, identities)
        items.append(
            MemberResponse(
                id=member.id,
                user_id=member.user_id,
                name=member.name,
                display_name=(
                    identity.display_name if identity else member.display_name or member.name
                ),
                avatar_url=identity.avatar_url if identity else member.avatar_url,
            ).model_dump()
        )
    return {"members": items}


@router.post("/{group_id}/members")
def add_member(group_id: UUID, payload: MemberAdd, db: Session = Depends(get_db)) -> dict:
    group = _get_group_or_404(db, group_id)
    hostname = payload.user_id.strip()
    user = consolidate_legacy_host_users(db, hostname)
    if user is None:
        user = find_legacy_host_user(db, hostname)
    if user is None:
        user = User(user_id=hostname, user_type=USER_TYPE_LEGACY_HOST)
        db.add(user)
        db.flush()
    user.group_id = group.id
    _sync_linked_person_group(db, user, group.id)
    db.commit()
    invalidate_group_cache(user.user_id)
    return _member_response(db, user)


@router.delete("/{group_id}/members/{user_id}")
def remove_member(group_id: UUID, user_id: str, db: Session = Depends(get_db)) -> dict:
    _get_group_or_404(db, group_id)
    user = (
        _legacy_members_query(db, group_id)
        .filter(User.user_id == user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Member not found in this group")
    # Realoca para o grupo Default (mantém a invariante "todo usuário tem um grupo").
    default_group = get_or_create_group(db, DEFAULT_GROUP_NAME)
    user.group_id = default_group.id
    _sync_linked_person_group(db, user, default_group.id)
    db.commit()
    invalidate_group_cache(user.user_id)
    return {"status": "moved_to_default"}
