"""add kanban_column_prompts table

Revision ID: o0d1e2f3g4h5
Revises: n9c0d1e2f3g4
Create Date: 2026-08-09 00:00:00.000000

Tarefa kanban-column-prompts. Cria a tabela kanban_column_prompts onde admins
podem personalizar o prompt de especificações retornado pelo MCP ao mover um
card para uma coluna do pipeline.

A tabela nasce vazia. Os prompts são cadastrados exclusivamente via a UI admin.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o0d1e2f3g4h5"
down_revision: Union[str, None] = "n9c0d1e2f3g4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "kanban_column_prompts" not in tables:
        op.create_table(
            "kanban_column_prompts",
            sa.Column(
                "column_status",
                sa.String(length=100),
                primary_key=True,
                nullable=False,
            ),
            sa.Column(
                "prompt",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("TRUE"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_by",
                sa.String(length=255),
                nullable=True,
            ),
            sa.CheckConstraint("LENGTH(prompt) <= 5000", name="chk_kanban_column_prompt_length"),
            comment="Prompts de especificação por coluna do pipeline Kanban",
        )


def downgrade() -> None:
    op.drop_table("kanban_column_prompts")
