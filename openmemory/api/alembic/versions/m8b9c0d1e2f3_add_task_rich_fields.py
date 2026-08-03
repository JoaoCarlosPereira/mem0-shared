"""add task rich fields (labels, checklists, attachments, members, due, position)

Revision ID: m8b9c0d1e2f3
Revises: l7a8b9c0d1e2
Create Date: 2026-08-03 00:00:00.000000

Kanban-planka task_05 / ADR-005. Spec remains SoT. Idempotent via inspect.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m8b9c0d1e2f3"
down_revision: Union[str, None] = "l7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "task_cards" in tables:
        cols = {c["name"] for c in inspector.get_columns("task_cards")}
        if "due_at" not in cols:
            op.add_column("task_cards", sa.Column("due_at", sa.DateTime(), nullable=True))
            op.create_index("ix_task_cards_due_at", "task_cards", ["due_at"])
        if "position" not in cols:
            op.add_column(
                "task_cards",
                sa.Column("position", sa.Float(), nullable=False, server_default="65536"),
            )

    if "task_labels" not in tables:
        op.create_table(
            "task_labels",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("workspace_id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("color", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["spec_workspaces.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workspace_id", "name", name="uq_task_label_workspace_name"),
        )
        op.create_index("ix_task_labels_workspace_id", "task_labels", ["workspace_id"])

    if "task_card_labels" not in tables:
        op.create_table(
            "task_card_labels",
            sa.Column("task_id", sa.UUID(), nullable=False),
            sa.Column("label_id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["task_id"], ["task_cards.id"]),
            sa.ForeignKeyConstraint(["label_id"], ["task_labels.id"]),
            sa.PrimaryKeyConstraint("task_id", "label_id"),
        )

    if "task_checklists" not in tables:
        op.create_table(
            "task_checklists",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("task_id", sa.UUID(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("position", sa.Float(), nullable=False, server_default="65536"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["task_cards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_task_checklists_task_id", "task_checklists", ["task_id"])

    if "task_checklist_items" not in tables:
        op.create_table(
            "task_checklist_items",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("checklist_id", sa.UUID(), nullable=False),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("is_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("position", sa.Float(), nullable=False, server_default="65536"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["checklist_id"], ["task_checklists.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_task_checklist_items_checklist_id", "task_checklist_items", ["checklist_id"])

    if "task_attachments" not in tables:
        op.create_table(
            "task_attachments",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("task_id", sa.UUID(), nullable=False),
            sa.Column("filename", sa.String(), nullable=False),
            sa.Column("content_type", sa.String(), nullable=True),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("storage_key", sa.String(), nullable=False),
            sa.Column("uploaded_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["task_cards.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_task_attachments_task_id", "task_attachments", ["task_id"])

    if "task_members" not in tables:
        op.create_table(
            "task_members",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("task_id", sa.UUID(), nullable=False),
            sa.Column("member", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["task_id"], ["task_cards.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", "member", name="uq_task_member"),
        )
        op.create_index("ix_task_members_task_id", "task_members", ["task_id"])


def downgrade() -> None:
    for table in (
        "task_members",
        "task_attachments",
        "task_checklist_items",
        "task_checklists",
        "task_card_labels",
        "task_labels",
    ):
        op.drop_table(table)
    op.drop_column("task_cards", "position")
    op.drop_index("ix_task_cards_due_at", table_name="task_cards")
    op.drop_column("task_cards", "due_at")
