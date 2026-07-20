"""add shared-specs tables (spec_workspaces, spec_documents, spec_document_versions,
task_cards, task_status_history, spec_audit_logs, spec_comments)

Revision ID: i4d5e6f7a8b9
Revises: h3c4d5e6f7a8
Create Date: 2026-07-20 00:00:00.000000

Espaço compartilhado de especificações (shared-specs / task_01 / ADR-004).

Cria a hierarquia ``Project → SpecWorkspace → (SpecDocument, TaskCard)`` mais o
histórico de versões por snapshot, o histórico de status de task, a trilha de
auditoria e os comentários. A migração é **aditiva e idempotente**: não altera
nenhuma tabela/coluna existente, não toca no Qdrant nem em memórias e pode ser
reexecutada com segurança (guardas via ``sa.inspect``). Enum nativo apenas no
PostgreSQL, no padrão de ``f5a6b7c8d9e0_add_governance_state.py``; em SQLite os
enums viram ``VARCHAR``.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i4d5e6f7a8b9"
down_revision: Union[str, None] = "h3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WORKSPACE_STATUS_VALUES = ("planejamento", "ativo", "concluido", "arquivado")
_TASK_STATUS_VALUES = ("tasks", "em_andamento", "revisao_codigo", "fase_teste", "concluido")
_DOCUMENT_TYPE_VALUES = ("prd", "techspec", "tasks")
_DOCUMENT_ORIGIN_VALUES = ("mcp", "ui", "api")
_COMMENT_TARGET_VALUES = ("workspace", "document", "task")


def _enum(values, name, is_pg):
    """Coluna de enum: nativa (referência) no PG, ``VARCHAR`` no SQLite."""
    if is_pg:
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.String()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    tables = set(inspector.get_table_names())

    if is_pg:
        postgresql.ENUM(*_WORKSPACE_STATUS_VALUES, name="specworkspacestatus").create(
            bind, checkfirst=True
        )
        postgresql.ENUM(*_TASK_STATUS_VALUES, name="taskcardstatus").create(
            bind, checkfirst=True
        )
        postgresql.ENUM(*_DOCUMENT_TYPE_VALUES, name="documenttype").create(
            bind, checkfirst=True
        )
        postgresql.ENUM(*_DOCUMENT_ORIGIN_VALUES, name="documentorigin").create(
            bind, checkfirst=True
        )
        postgresql.ENUM(*_COMMENT_TARGET_VALUES, name="commenttargettype").create(
            bind, checkfirst=True
        )

    # 1) spec_workspaces (FK -> projects.name)
    if "spec_workspaces" not in tables:
        op.create_table(
            "spec_workspaces",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("project_id", sa.String(), nullable=False),
            sa.Column("slug", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column(
                "status",
                _enum(_WORKSPACE_STATUS_VALUES, "specworkspacestatus", is_pg),
                nullable=False,
                server_default="planejamento",
            ),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.name"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "slug", name="uq_spec_workspace_project_slug"),
        )
        op.create_index(op.f("ix_spec_workspaces_project_id"), "spec_workspaces", ["project_id"])
        op.create_index(op.f("ix_spec_workspaces_slug"), "spec_workspaces", ["slug"])
        op.create_index(op.f("ix_spec_workspaces_status"), "spec_workspaces", ["status"])
        op.create_index(op.f("ix_spec_workspaces_created_at"), "spec_workspaces", ["created_at"])

    # 2) spec_documents (FK -> spec_workspaces.id)
    if "spec_documents" not in tables:
        op.create_table(
            "spec_documents",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("workspace_id", sa.UUID(), nullable=False),
            sa.Column(
                "document_type",
                _enum(_DOCUMENT_TYPE_VALUES, "documenttype", is_pg),
                nullable=False,
            ),
            sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("current_content", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["spec_workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "workspace_id", "document_type", name="uq_spec_document_workspace_type"
            ),
        )
        op.create_index(
            op.f("ix_spec_documents_workspace_id"), "spec_documents", ["workspace_id"]
        )
        op.create_index(
            op.f("ix_spec_documents_created_at"), "spec_documents", ["created_at"]
        )

    # 3) spec_document_versions (FK -> spec_documents.id)
    if "spec_document_versions" not in tables:
        op.create_table(
            "spec_document_versions",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("document_id", sa.UUID(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("author", sa.String(), nullable=True),
            sa.Column(
                "origin",
                _enum(_DOCUMENT_ORIGIN_VALUES, "documentorigin", is_pg),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["document_id"], ["spec_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "document_id", "version", name="uq_spec_version_document_version"
            ),
        )
        op.create_index(
            op.f("ix_spec_document_versions_document_id"),
            "spec_document_versions",
            ["document_id"],
        )
        op.create_index(
            op.f("ix_spec_document_versions_created_at"),
            "spec_document_versions",
            ["created_at"],
        )

    # 4) task_cards (FK -> spec_workspaces.id)
    if "task_cards" not in tables:
        op.create_table(
            "task_cards",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("workspace_id", sa.UUID(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "status",
                _enum(_TASK_STATUS_VALUES, "taskcardstatus", is_pg),
                nullable=False,
                server_default="tasks",
            ),
            sa.Column(
                "is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("block_reason", sa.Text(), nullable=True),
            sa.Column("assignee", sa.String(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("last_activity_at", sa.DateTime(), nullable=True),
            sa.Column("branch_ref", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["spec_workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_task_cards_workspace_id"), "task_cards", ["workspace_id"])
        op.create_index(op.f("ix_task_cards_status"), "task_cards", ["status"])
        op.create_index(op.f("ix_task_cards_assignee"), "task_cards", ["assignee"])
        op.create_index(
            op.f("ix_task_cards_last_activity_at"), "task_cards", ["last_activity_at"]
        )
        op.create_index(op.f("ix_task_cards_created_at"), "task_cards", ["created_at"])
        op.create_index(
            "idx_task_card_workspace_status", "task_cards", ["workspace_id", "status"]
        )

    # 5) task_status_history (FK -> task_cards.id)
    if "task_status_history" not in tables:
        op.create_table(
            "task_status_history",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("task_id", sa.UUID(), nullable=False),
            sa.Column(
                "old_status",
                _enum(_TASK_STATUS_VALUES, "taskcardstatus", is_pg),
                nullable=False,
            ),
            sa.Column(
                "new_status",
                _enum(_TASK_STATUS_VALUES, "taskcardstatus", is_pg),
                nullable=False,
            ),
            sa.Column("changed_by", sa.String(), nullable=True),
            sa.Column("changed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["task_cards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_task_status_history_task_id"), "task_status_history", ["task_id"]
        )
        op.create_index(
            op.f("ix_task_status_history_old_status"),
            "task_status_history",
            ["old_status"],
        )
        op.create_index(
            op.f("ix_task_status_history_new_status"),
            "task_status_history",
            ["new_status"],
        )
        op.create_index(
            op.f("ix_task_status_history_changed_by"),
            "task_status_history",
            ["changed_by"],
        )
        op.create_index(
            op.f("ix_task_status_history_changed_at"),
            "task_status_history",
            ["changed_at"],
        )
        op.create_index(
            "idx_task_history_task_status", "task_status_history", ["task_id", "new_status"]
        )
        op.create_index(
            "idx_task_history_actor_time",
            "task_status_history",
            ["changed_by", "changed_at"],
        )

    # 6) spec_audit_logs (FK -> spec_workspaces.id)
    if "spec_audit_logs" not in tables:
        op.create_table(
            "spec_audit_logs",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("workspace_id", sa.UUID(), nullable=False),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=True),
            sa.Column(
                "origin",
                _enum(_DOCUMENT_ORIGIN_VALUES, "documentorigin", is_pg),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["spec_workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_spec_audit_logs_workspace_id"), "spec_audit_logs", ["workspace_id"]
        )
        op.create_index(op.f("ix_spec_audit_logs_actor"), "spec_audit_logs", ["actor"])
        op.create_index(op.f("ix_spec_audit_logs_action"), "spec_audit_logs", ["action"])
        op.create_index(
            op.f("ix_spec_audit_logs_created_at"), "spec_audit_logs", ["created_at"]
        )

    # 7) spec_comments (referência polimórfica, sem FK física)
    if "spec_comments" not in tables:
        op.create_table(
            "spec_comments",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column(
                "target_type",
                _enum(_COMMENT_TARGET_VALUES, "commenttargettype", is_pg),
                nullable=False,
            ),
            sa.Column("target_id", sa.UUID(), nullable=False),
            sa.Column("author", sa.String(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_spec_comments_target_type"), "spec_comments", ["target_type"]
        )
        op.create_index(
            op.f("ix_spec_comments_target_id"), "spec_comments", ["target_id"]
        )
        op.create_index(
            op.f("ix_spec_comments_created_at"), "spec_comments", ["created_at"]
        )
        op.create_index(
            "idx_spec_comment_target", "spec_comments", ["target_type", "target_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    tables = set(inspector.get_table_names())

    # Ordem inversa de criação (respeitando FKs).
    for table in (
        "spec_comments",
        "spec_audit_logs",
        "task_status_history",
        "task_cards",
        "spec_document_versions",
        "spec_documents",
        "spec_workspaces",
    ):
        if table in tables:
            op.drop_table(table)

    if is_pg:
        postgresql.ENUM(name="commenttargettype").drop(bind, checkfirst=True)
        postgresql.ENUM(name="documentorigin").drop(bind, checkfirst=True)
        postgresql.ENUM(name="documenttype").drop(bind, checkfirst=True)
        postgresql.ENUM(name="taskcardstatus").drop(bind, checkfirst=True)
        postgresql.ENUM(name="specworkspacestatus").drop(bind, checkfirst=True)
