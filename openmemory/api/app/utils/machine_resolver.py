"""Resolução canônica de máquinas e vínculo com usuários legados (ADR-004/ADR-005).

O onboarding normaliza hostnames Sysmo para maiúsculas (``S0281``), mas conexões
MCP anteriores podem ter registrado a mesma máquina em minúsculas (``s0281``) ou com
casing divergente (``Hermes`` vs ``hermes``) via ``ensure_user_group``. Isso gerava
linhas duplicadas em ``machines``/``users``, perda de ``legacy_user_id`` e membros
duplicados no Admin.

Este módulo centraliza lookup case-insensitive, fusão de duplicatas e backfill de
``legacy_user_id``.
"""

from __future__ import annotations

from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    USER_TYPE_LEGACY_HOST,
    AgentToken,
    App,
    Machine,
    MachineStatus,
    Memory,
    MemoryAccessLog,
    MemoryStatusHistory,
    User,
    memory_categories,
)
from app.utils.hostname_validation import normalize_sysmo_hostname
from app.utils.identity import DEFAULT_HOSTNAME, resolve_hostname


def canonical_machine_hostname(raw: str | None) -> str:
    """Hostname canônico para catálogo de máquinas e usuários legados."""
    base = resolve_hostname(raw)
    if base == DEFAULT_HOSTNAME:
        return base
    normalized = normalize_sysmo_hostname(base)
    return normalized if normalized is not None else base


def is_sysmo_machine_hostname(hostname: str) -> bool:
    return normalize_sysmo_hostname(hostname) is not None


def _prefer_hostname_casing(candidates: list[str]) -> str:
    """Prefere casing com letras maiúsculas (ex.: ``Hermes`` sobre ``hermes``)."""
    if not candidates:
        return ""
    scored = sorted(
        candidates,
        key=lambda value: (
            sum(1 for ch in value if ch.isupper()),
            len(value),
            value,
        ),
        reverse=True,
    )
    return scored[0]


def find_legacy_host_user(db: Session, hostname: str) -> Optional[User]:
    """Usuário ``legacy_host`` cujo ``user_id`` corresponde ao hostname."""
    canonical = canonical_machine_hostname(hostname)
    user = (
        db.query(User)
        .filter(User.user_id == canonical, User.user_type == USER_TYPE_LEGACY_HOST)
        .first()
    )
    if user is not None:
        return user
    return (
        db.query(User)
        .filter(
            User.user_type == USER_TYPE_LEGACY_HOST,
            func.lower(User.user_id) == canonical.lower(),
        )
        .first()
    )


def legacy_hostname_variants(db: Session, hostname: str) -> list[str]:
    """Todas as grafias conhecidas de um hostname legado (SQL + máquina)."""
    canonical = canonical_machine_hostname(hostname)
    if not canonical:
        return []
    variants = {canonical}
    for (user_id,) in (
        db.query(User.user_id)
        .filter(
            User.user_type == USER_TYPE_LEGACY_HOST,
            func.lower(User.user_id) == canonical.lower(),
        )
        .all()
    ):
        variants.add(user_id)
    machine = find_machine(db, canonical)
    if machine is not None:
        variants.add(machine.hostname)
    return sorted(variants)


def find_machine(db: Session, hostname: str) -> Optional[Machine]:
    """Busca máquina por hostname exato ou case-insensitive."""
    canonical = canonical_machine_hostname(hostname)
    machine = db.query(Machine).filter(Machine.hostname == canonical).first()
    if machine is not None:
        return machine
    return (
        db.query(Machine)
        .filter(func.lower(Machine.hostname) == canonical.lower())
        .first()
    )


def _machine_variants(db: Session, hostname: str) -> list[Machine]:
    canonical = canonical_machine_hostname(hostname)
    return (
        db.query(Machine)
        .filter(func.lower(Machine.hostname) == canonical.lower())
        .order_by(Machine.hostname)
        .all()
    )


def _legacy_host_user_variants(db: Session, hostname: str) -> list[User]:
    canonical = canonical_machine_hostname(hostname)
    return (
        db.query(User)
        .filter(
            User.user_type == USER_TYPE_LEGACY_HOST,
            func.lower(User.user_id) == canonical.lower(),
        )
        .order_by(User.created_at)
        .all()
    )


def _pick_canonical_user_id(db: Session, variants: list[User], machine: Optional[Machine]) -> str:
    if machine is not None:
        return machine.hostname
    if variants:
        machine = find_machine(db, variants[0].user_id)
        if machine is not None:
            return machine.hostname
    return _prefer_hostname_casing([user.user_id for user in variants])


def _merge_legacy_user_rows(
    db: Session,
    *,
    duplicate: User,
    target: User,
) -> User:
    """Funde ``duplicate`` em ``target`` e remove a linha duplicada."""
    if duplicate.id == target.id:
        return target

    dup_id: UUID = duplicate.id
    tgt_id: UUID = target.id

    memory_ids = [row[0] for row in db.query(Memory.id).filter(Memory.user_id == dup_id).all()]
    if memory_ids:
        db.query(MemoryStatusHistory).filter(
            MemoryStatusHistory.memory_id.in_(memory_ids)
        ).delete(synchronize_session=False)
        db.query(MemoryAccessLog).filter(MemoryAccessLog.memory_id.in_(memory_ids)).delete(
            synchronize_session=False
        )
        db.execute(
            memory_categories.delete().where(memory_categories.c.memory_id.in_(memory_ids))
        )
        db.query(Memory).filter(Memory.user_id == dup_id).update(
            {Memory.user_id: tgt_id},
            synchronize_session=False,
        )

    for app in db.query(App).filter(App.owner_id == dup_id).all():
        existing = (
            db.query(App)
            .filter(App.owner_id == tgt_id, App.name == app.name)
            .first()
        )
        if existing is not None:
            db.query(MemoryAccessLog).filter(MemoryAccessLog.app_id == app.id).update(
                {MemoryAccessLog.app_id: existing.id},
                synchronize_session=False,
            )
            db.delete(app)
        else:
            app.owner_id = tgt_id

    db.query(AgentToken).filter(AgentToken.user_id == dup_id).update(
        {AgentToken.user_id: tgt_id},
        synchronize_session=False,
    )

    for machine in db.query(Machine).filter(Machine.legacy_user_id == dup_id).all():
        if machine.legacy_user_id != tgt_id:
            machine.legacy_user_id = tgt_id
    for machine in db.query(Machine).filter(Machine.linked_by == dup_id).all():
        machine.linked_by = tgt_id

    if target.group_id is None and duplicate.group_id is not None:
        target.group_id = duplicate.group_id

    db.delete(duplicate)
    db.flush()
    return target


def consolidate_legacy_host_users(db: Session, hostname: str) -> Optional[User]:
    """Funde usuários ``legacy_host`` com o mesmo hostname (case-insensitive)."""
    variants = _legacy_host_user_variants(db, hostname)
    if not variants:
        return None

    machine = find_machine(db, hostname)
    canonical_user_id = _pick_canonical_user_id(db, variants, machine)

    target = next((user for user in variants if user.user_id == canonical_user_id), variants[0])
    for duplicate in variants:
        if duplicate.id != target.id:
            target = _merge_legacy_user_rows(db, duplicate=duplicate, target=target)

    if target.user_id != canonical_user_id:
        existing = (
            db.query(User)
            .filter(User.user_id == canonical_user_id, User.user_type == USER_TYPE_LEGACY_HOST)
            .first()
        )
        if existing is None:
            target.user_id = canonical_user_id
            db.flush()

    if machine is not None:
        machine.legacy_user_id = target.id

    return target


def _merge_machine_rows(db: Session, *, duplicate: Machine, target: Machine) -> Machine:
    """Funde ``duplicate`` em ``target`` e remove a linha duplicada."""
    if duplicate.id == target.id:
        return target

    from app.models import LinkAuditLog

    db.query(LinkAuditLog).filter(LinkAuditLog.machine_id == duplicate.id).update(
        {LinkAuditLog.machine_id: target.id},
        synchronize_session=False,
    )

    if target.legacy_user_id is None and duplicate.legacy_user_id is not None:
        target.legacy_user_id = duplicate.legacy_user_id

    if target.linked_user_id is None and duplicate.linked_user_id is not None:
        target.linked_user_id = duplicate.linked_user_id
        target.status = duplicate.status
        target.linked_at = duplicate.linked_at
        target.linked_by = duplicate.linked_by
    elif (
        duplicate.linked_user_id is not None
        and target.linked_user_id is not None
        and duplicate.linked_user_id != target.linked_user_id
    ):
        target.status = MachineStatus.conflict

    db.delete(duplicate)
    db.flush()
    return target


def _canonicalize_machine_hostname(db: Session, machine: Machine, canonical: str) -> Machine:
    """Garante uma única linha com hostname canônico."""
    if machine.hostname == canonical:
        return machine

    existing = db.query(Machine).filter(Machine.hostname == canonical).first()
    if existing is not None:
        return _merge_machine_rows(db, duplicate=machine, target=existing)

    machine.hostname = canonical
    db.flush()
    return machine


def _consolidate_machine_variants(db: Session, hostname: str) -> Optional[Machine]:
    """Funde variantes case-insensitive numa única linha canônica."""
    variants = _machine_variants(db, hostname)
    if not variants:
        return None

    canonical = canonical_machine_hostname(hostname)
    if is_sysmo_machine_hostname(canonical):
        target_hostname = canonical
    else:
        target_hostname = _prefer_hostname_casing([machine.hostname for machine in variants])

    target = next((machine for machine in variants if machine.hostname == target_hostname), variants[0])
    if target.hostname != target_hostname:
        target = _canonicalize_machine_hostname(db, target, target_hostname)

    for duplicate in variants:
        if duplicate.id != target.id:
            target = _merge_machine_rows(db, duplicate=duplicate, target=target)

    return target


def consolidate_group_legacy_members(db: Session, group_id: UUID) -> None:
    """Funde duplicatas case-insensitive entre membros legados de um grupo."""
    members = (
        db.query(User)
        .filter(User.group_id == group_id, User.user_type == USER_TYPE_LEGACY_HOST)
        .all()
    )
    seen: set[str] = set()
    dirty = False
    for member in members:
        key = member.user_id.lower()
        if key in seen:
            consolidate_legacy_host_users(db, member.user_id)
            dirty = True
        else:
            seen.add(key)
    if dirty:
        db.commit()


def backfill_legacy_user_id(machine: Machine, legacy_user: Optional[User]) -> None:
    if legacy_user is not None and machine.legacy_user_id is None:
        machine.legacy_user_id = legacy_user.id


def resolve_or_create_machine(
    db: Session, hostname: str
) -> Tuple[Machine, Optional[User]]:
    """Resolve máquina + legado com hostname canônico e sem duplicata case."""
    canonical = canonical_machine_hostname(hostname)
    legacy_user = consolidate_legacy_host_users(db, canonical)
    if legacy_user is None:
        legacy_user = find_legacy_host_user(db, canonical)

    machine = _consolidate_machine_variants(db, canonical)
    if machine is not None and is_sysmo_machine_hostname(canonical):
        machine = _canonicalize_machine_hostname(db, machine, canonical)
    elif machine is not None and not is_sysmo_machine_hostname(canonical):
        preferred = _prefer_hostname_casing([machine.hostname, canonical])
        if machine.hostname != preferred:
            machine = _canonicalize_machine_hostname(db, machine, preferred)

    if machine is None:
        user_id = legacy_user.user_id if legacy_user is not None else canonical
        machine = Machine(
            hostname=user_id,
            legacy_user_id=legacy_user.id if legacy_user is not None else None,
        )
        db.add(machine)
        db.flush()
    else:
        backfill_legacy_user_id(machine, legacy_user)

    if legacy_user is not None:
        machine.legacy_user_id = legacy_user.id

    return machine, legacy_user
