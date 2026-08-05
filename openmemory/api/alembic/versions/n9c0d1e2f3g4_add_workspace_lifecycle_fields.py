"""add workspace lifecycle timestamps (completed_at, archived_at, archived_by)

Revision ID: n9c0d1e2f3g4
Revises: m8b9c0d1e2f3
Create Date: 2026-08-05 00:00:00.000000

Tarefa kanban-archive-lifecycle. Spec (``spec_workspaces.status``) remains SoT;
these columns only record *when*/*by whom* the concluido/arquivado transitions
happened, since ``updated_at`` is overwritten by unrelated edits. Idempotent
via inspect, same convention as m8b9c0d1e2f3.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n9c0d1e2f3g4"
down_revision: Union[str, None] = "m8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "spec_workspaces" in tables:
        cols = {c["name"] for c in inspector.get_columns("spec_workspaces")}
        if "completed_at" not in cols:
            op.add_column("spec_workspaces", sa.Column("completed_at", sa.DateTime(), nullable=True))
        if "archived_at" not in cols:
            op.add_column("spec_workspaces", sa.Column("archived_at", sa.DateTime(), nullable=True))
        if "archived_by" not in cols:
            op.add_column("spec_workspaces", sa.Column("archived_by", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("spec_workspaces", "archived_by")
    op.drop_column("spec_workspaces", "archived_at")
    op.drop_column("spec_workspaces", "completed_at")
