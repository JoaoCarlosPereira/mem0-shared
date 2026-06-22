"""add merge_projects governance job type

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-22 00:00:00.000000

Adds ``merge_projects`` to the PostgreSQL ``governancejobtype`` enum for
LLM-assisted duplicate project unification.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_JOB_TYPES = ("merge_projects",)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for value in _NEW_JOB_TYPES:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = 'governancejobtype' AND e.enumlabel = :v"
            ),
            {"v": value},
        ).scalar()
        if not exists:
            op.execute(f"ALTER TYPE governancejobtype ADD VALUE '{value}'")


def downgrade() -> None:
    # PostgreSQL cannot drop a single enum label safely.
    pass
