"""add read_audit_logs for Qdrant/MCP memory access tracking

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-22 12:00:00.000000

Records search/list/get access to memories that live in Qdrant (MCP path) so the
Apps dashboard can show Memórias Acessadas per project.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "read_audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project", sa.String(), nullable=False),
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("access_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("hostname", sa.String(), nullable=False),
        sa.Column("client_name", sa.String(), nullable=True),
        sa.Column("query", sa.String(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_read_audit_logs_project"), "read_audit_logs", ["project"])
    op.create_index(op.f("ix_read_audit_logs_memory_id"), "read_audit_logs", ["memory_id"])
    op.create_index(op.f("ix_read_audit_logs_access_type"), "read_audit_logs", ["access_type"])
    op.create_index(op.f("ix_read_audit_logs_source"), "read_audit_logs", ["source"])
    op.create_index(op.f("ix_read_audit_logs_hostname"), "read_audit_logs", ["hostname"])
    op.create_index(op.f("ix_read_audit_logs_accessed_at"), "read_audit_logs", ["accessed_at"])
    op.create_index("idx_read_audit_project_time", "read_audit_logs", ["project", "accessed_at"])
    op.create_index("idx_read_audit_memory_time", "read_audit_logs", ["memory_id", "accessed_at"])
    op.create_index("idx_read_audit_project_memory", "read_audit_logs", ["project", "memory_id"])


def downgrade() -> None:
    op.drop_index("idx_read_audit_project_memory", table_name="read_audit_logs")
    op.drop_index("idx_read_audit_memory_time", table_name="read_audit_logs")
    op.drop_index("idx_read_audit_project_time", table_name="read_audit_logs")
    op.drop_index(op.f("ix_read_audit_logs_accessed_at"), table_name="read_audit_logs")
    op.drop_index(op.f("ix_read_audit_logs_hostname"), table_name="read_audit_logs")
    op.drop_index(op.f("ix_read_audit_logs_source"), table_name="read_audit_logs")
    op.drop_index(op.f("ix_read_audit_logs_access_type"), table_name="read_audit_logs")
    op.drop_index(op.f("ix_read_audit_logs_memory_id"), table_name="read_audit_logs")
    op.drop_index(op.f("ix_read_audit_logs_project"), table_name="read_audit_logs")
    op.drop_table("read_audit_logs")
