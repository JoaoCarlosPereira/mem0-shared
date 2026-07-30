"""add write_queue.extras JSON for supersedes metadata

Revision ID: j5e6f7a8b9c0
Revises: i4d5e6f7a8b9
Create Date: 2026-07-30 00:00:00.000000

Additive column ``extras`` (JSON, nullable) on ``write_queue`` so MCP can pass
``supersedes`` (and future write options) without new columns per feature.
Does not touch Qdrant or existing jobs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j5e6f7a8b9c0"
down_revision: Union[str, None] = "i4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("write_queue")}
    if "extras" not in cols:
        op.add_column("write_queue", sa.Column("extras", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("write_queue")}
    if "extras" in cols:
        op.drop_column("write_queue", "extras")
