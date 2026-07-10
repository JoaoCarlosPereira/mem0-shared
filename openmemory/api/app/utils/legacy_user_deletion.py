"""Exclusão permanente de usuários legados (hostname) no catálogo SQL.

Remove a linha em ``users`` e metadados SQL associados (apps, memories). Não
toca payloads no Qdrant — memórias vetoriais permanecem indexadas pelo hostname
no payload, conforme ADR-005.
"""

from __future__ import annotations

import os
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    AgentToken,
    App,
    Machine,
    Memory,
    MemoryAccessLog,
    MemoryStatusHistory,
    User,
    USER_TYPE_LEGACY_HOST,
    USER_TYPE_PERSON,
    memory_categories,
)
from app.utils.groups import invalidate_group_cache
from app.utils.identity_links import invalidate_identity_link_cache
from app.utils.machine_resolver import find_legacy_host_user, find_machine

_PROTECTED_USER_IDS = frozenset(
    {
        os.getenv("USER", "openmemory"),
        "openmemory",
        "default_user",
    }
)


def _protected_user_ids() -> frozenset[str]:
    return _PROTECTED_USER_IDS


def purge_legacy_host_user(db: Session, hostname: str) -> dict:
    """Remove usuário legado e catálogo SQL; memórias no Qdrant não são alteradas."""
    hostname = (hostname or "").strip()
    if not hostname:
        raise HTTPException(status_code=422, detail="hostname obrigatório")

    if hostname in _protected_user_ids():
        raise HTTPException(
            status_code=403,
            detail="este usuário do sistema não pode ser removido",
        )

    user = find_legacy_host_user(db, hostname)
    if user is None:
        person = (
            db.query(User)
            .filter(User.user_id == hostname, User.user_type == USER_TYPE_PERSON)
            .first()
        )
        if person is not None:
            raise HTTPException(
                status_code=403,
                detail="contas Google (person) não podem ser excluídas por este endpoint",
            )
        raise HTTPException(status_code=404, detail="usuário legado não encontrado")

    user_pk: UUID = user.id
    hostname_key = user.user_id

    memory_ids = [
        row[0]
        for row in db.query(Memory.id).filter(Memory.user_id == user_pk).all()
    ]
    if memory_ids:
        db.query(MemoryStatusHistory).filter(
            MemoryStatusHistory.memory_id.in_(memory_ids)
        ).delete(synchronize_session=False)
        db.query(MemoryAccessLog).filter(
            MemoryAccessLog.memory_id.in_(memory_ids)
        ).delete(synchronize_session=False)
        db.execute(
            memory_categories.delete().where(
                memory_categories.c.memory_id.in_(memory_ids)
            )
        )
        db.query(Memory).filter(Memory.user_id == user_pk).delete(
            synchronize_session=False
        )

    app_ids = [row[0] for row in db.query(App.id).filter(App.owner_id == user_pk).all()]
    if app_ids:
        db.query(MemoryAccessLog).filter(MemoryAccessLog.app_id.in_(app_ids)).delete(
            synchronize_session=False
        )
        db.query(App).filter(App.owner_id == user_pk).delete(synchronize_session=False)

    db.query(AgentToken).filter(AgentToken.user_id == user_pk).delete(
        synchronize_session=False
    )

    for machine in db.query(Machine).filter(Machine.legacy_user_id == user_pk).all():
        machine.legacy_user_id = None
    for machine in db.query(Machine).filter(Machine.linked_by == user_pk).all():
        machine.linked_by = None

    db.delete(user)
    db.commit()

    invalidate_group_cache(hostname_key)
    invalidate_identity_link_cache(hostname_key)
    machine = find_machine(db, hostname_key)
    if machine is not None:
        invalidate_identity_link_cache(machine.hostname)

    return {
        "status": "deleted",
        "user_id": hostname_key,
        "sql_memories_removed": len(memory_ids),
        "qdrant_preserved": True,
    }
