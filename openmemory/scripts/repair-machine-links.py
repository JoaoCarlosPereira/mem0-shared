#!/usr/bin/env python3
"""Repara vínculos máquina↔legado e funde duplicatas case-insensitive (Sysmo S####).

Uso:
  DATABASE_URL=postgresql://... python openmemory/scripts/repair-machine-links.py
  python openmemory/scripts/repair-machine-links.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../api")))

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from app.database import engine
from app.models import USER_TYPE_LEGACY_HOST, Machine, MachineStatus, User
from app.utils.machine_resolver import (
    backfill_legacy_user_id,
    canonical_machine_hostname,
    consolidate_legacy_host_users,
    find_legacy_host_user,
    find_machine,
    is_sysmo_machine_hostname,
    resolve_or_create_machine,
)


def repair(dry_run: bool = False) -> None:
    Session = sessionmaker(bind=engine)
    db = Session()
    merged = 0
    backfilled = 0
    try:
        # 1) Fundir duplicatas de máquinas (case-insensitive)
        rows = (
            db.query(func.lower(Machine.hostname).label("key"))
            .group_by(func.lower(Machine.hostname))
            .having(func.count(Machine.id) > 1)
            .all()
        )
        for (key,) in rows:
            canonical = canonical_machine_hostname(key)
            machines = (
                db.query(Machine)
                .filter(func.lower(Machine.hostname) == key.lower())
                .order_by(Machine.hostname)
                .all()
            )
            print(f"Merge máquinas {key!r} -> {canonical!r}: {[m.hostname for m in machines]}")
            _, _ = resolve_or_create_machine(db, canonical)
            merged += 1

        # 1b) Fundir duplicatas de usuários legados (case-insensitive)
        user_dupes = (
            db.query(func.lower(User.user_id).label("key"))
            .filter(User.user_type == USER_TYPE_LEGACY_HOST)
            .group_by(func.lower(User.user_id))
            .having(func.count(User.id) > 1)
            .all()
        )
        users_merged = 0
        for (key,) in user_dupes:
            variants = (
                db.query(User.user_id)
                .filter(
                    User.user_type == USER_TYPE_LEGACY_HOST,
                    func.lower(User.user_id) == key.lower(),
                )
                .all()
            )
            print(f"Merge usuários legados {key!r}: {[v[0] for v in variants]}")
            consolidate_legacy_host_users(db, key)
            users_merged += 1

        # 2) Backfill legacy_user_id em máquinas vinculadas ou catalogadas
        for machine in db.query(Machine).all():
            legacy = find_legacy_host_user(db, machine.hostname)
            before = machine.legacy_user_id
            backfill_legacy_user_id(machine, legacy)
            if machine.legacy_user_id != before:
                print(
                    f"Backfill {machine.hostname}: legacy_user_id "
                    f"{before} -> {machine.legacy_user_id}"
                )
                backfilled += 1

        # 3) Sincronizar grupo legado com pessoa vinculada (quando aplicável)
        for machine in db.query(Machine).filter(Machine.status == MachineStatus.linked).all():
            if machine.linked_user_id is None or machine.legacy_user_id is None:
                continue
            person = db.query(User).filter(User.id == machine.linked_user_id).first()
            legacy = db.query(User).filter(User.id == machine.legacy_user_id).first()
            if (
                person is not None
                and legacy is not None
                and person.group_id is not None
                and legacy.group_id != person.group_id
            ):
                print(
                    f"Sync grupo legado {legacy.user_id}: "
                    f"{legacy.group_id} -> {person.group_id}"
                )
                legacy.group_id = person.group_id

        if dry_run:
            db.rollback()
            print(f"[dry-run] merged_machines={merged} merged_users={users_merged} backfilled={backfilled}")
        else:
            db.commit()
            print(f"OK merged_machines={merged} merged_users={users_merged} backfilled={backfilled}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Repara vínculos machines↔legacy_host")
    parser.add_argument("--dry-run", action="store_true", help="Não grava alterações")
    args = parser.parse_args()
    repair(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
