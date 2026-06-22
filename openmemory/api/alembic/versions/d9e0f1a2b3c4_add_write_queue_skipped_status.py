"""add write_queue skipped status

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-22 14:00:00.000000

Adds ``skipped`` to the PostgreSQL ``writequeuestatus`` enum for jobs that were
processed successfully but produced no new memories (duplicate or not useful).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_STATUSES = ("skipped",)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for value in _NEW_STATUSES:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = 'writequeuestatus' AND e.enumlabel = :v"
            ),
            {"v": value},
        ).scalar()
        if not exists:
            op.execute(f"ALTER TYPE writequeuestatus ADD VALUE '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum label safely.
    pass
