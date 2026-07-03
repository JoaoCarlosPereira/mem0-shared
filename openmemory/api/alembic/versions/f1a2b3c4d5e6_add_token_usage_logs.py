"""add token_usage_logs for LLM/embedding token metrics

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-07-02 12:00:00.000000

Uma linha por chamada LLM/embedding instrumentada (métricas de consumo de
tokens — PRD metricas-consumo-recursos, task_01). Índices compostos por
dimensão + created_at para consultas agregadas por período.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e0f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_usage_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("project", sa.String(), nullable=False),
        sa.Column("agent", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("operation_type", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_usage_logs_created_at"), "token_usage_logs", ["created_at"])
    op.create_index(op.f("ix_token_usage_logs_project"), "token_usage_logs", ["project"])
    op.create_index(op.f("ix_token_usage_logs_agent"), "token_usage_logs", ["agent"])
    op.create_index(op.f("ix_token_usage_logs_user_id"), "token_usage_logs", ["user_id"])
    op.create_index(op.f("ix_token_usage_logs_operation_type"), "token_usage_logs", ["operation_type"])
    op.create_index(op.f("ix_token_usage_logs_model"), "token_usage_logs", ["model"])
    op.create_index("idx_token_usage_project_time", "token_usage_logs", ["project", "created_at"])
    op.create_index("idx_token_usage_agent_time", "token_usage_logs", ["agent", "created_at"])
    op.create_index("idx_token_usage_user_time", "token_usage_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_token_usage_user_time", table_name="token_usage_logs")
    op.drop_index("idx_token_usage_agent_time", table_name="token_usage_logs")
    op.drop_index("idx_token_usage_project_time", table_name="token_usage_logs")
    op.drop_index(op.f("ix_token_usage_logs_model"), table_name="token_usage_logs")
    op.drop_index(op.f("ix_token_usage_logs_operation_type"), table_name="token_usage_logs")
    op.drop_index(op.f("ix_token_usage_logs_user_id"), table_name="token_usage_logs")
    op.drop_index(op.f("ix_token_usage_logs_agent"), table_name="token_usage_logs")
    op.drop_index(op.f("ix_token_usage_logs_project"), table_name="token_usage_logs")
    op.drop_index(op.f("ix_token_usage_logs_created_at"), table_name="token_usage_logs")
    op.drop_table("token_usage_logs")
