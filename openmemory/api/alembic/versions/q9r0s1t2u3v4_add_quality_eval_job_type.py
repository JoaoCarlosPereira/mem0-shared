"""add quality_eval governance job type

Revision ID: q9r0s1t2u3v4
Revises: q2f3g4h5i6j7
Create Date: 2026-08-29 00:00:00.000000

Adds ``quality_eval`` to the PostgreSQL ``governancejobtype`` enum so the
search-quality evaluation job is a first-class, individually toggleable
process (it previously shared the ``consolidate`` enum bucket/schedule row).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q9r0s1t2u3v4"
down_revision: Union[str, None] = "q2f3g4h5i6j7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_JOB_TYPES = ("quality_eval",)


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
