"""add adrs document type

Revision ID: k6f7a8b9c0d1
Revises: j5e6f7a8b9c0
Create Date: 2026-07-30 00:00:00.000000

Adds ``adrs`` to the PostgreSQL ``documenttype`` enum so workspaces can store
a versioned Architecture Decision Records document (not a Kanban card).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k6f7a8b9c0d1"
down_revision: Union[str, None] = "j5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_VALUES = ("adrs",)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for value in _NEW_VALUES:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = 'documenttype' AND e.enumlabel = :v"
            ),
            {"v": value},
        ).scalar()
        if not exists:
            op.execute(f"ALTER TYPE documenttype ADD VALUE '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum label safely.
    pass
