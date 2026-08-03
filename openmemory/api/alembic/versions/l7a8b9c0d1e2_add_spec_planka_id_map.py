"""add spec_planka_id_map for Spec ↔ PLANKA id correlation

Revision ID: l7a8b9c0d1e2
Revises: k6f7a8b9c0d1
Create Date: 2026-08-03 00:00:00.000000

Additive table ``spec_planka_id_map`` (kanban-planka / task_02 / ADR-005).
Maps Spec UUIDs to PLANKA snowflake IDs. Idempotent via ``sa.inspect``.
Does not touch Qdrant or existing Spec tables.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l7a8b9c0d1e2"
down_revision: Union[str, None] = "k6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "spec_planka_id_map" not in tables:
        op.create_table(
            "spec_planka_id_map",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("spec_id", sa.UUID(), nullable=False),
            sa.Column("planka_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "entity_type", "spec_id", name="uq_spec_planka_entity_spec"
            ),
            sa.UniqueConstraint(
                "entity_type", "planka_id", name="uq_spec_planka_entity_planka"
            ),
        )
        op.create_index(
            op.f("ix_spec_planka_id_map_entity_type"),
            "spec_planka_id_map",
            ["entity_type"],
        )
        op.create_index(
            op.f("ix_spec_planka_id_map_spec_id"),
            "spec_planka_id_map",
            ["spec_id"],
        )
        op.create_index(
            op.f("ix_spec_planka_id_map_planka_id"),
            "spec_planka_id_map",
            ["planka_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "spec_planka_id_map" in tables:
        op.drop_index(op.f("ix_spec_planka_id_map_planka_id"), table_name="spec_planka_id_map")
        op.drop_index(op.f("ix_spec_planka_id_map_spec_id"), table_name="spec_planka_id_map")
        op.drop_index(op.f("ix_spec_planka_id_map_entity_type"), table_name="spec_planka_id_map")
        op.drop_table("spec_planka_id_map")
