"""add groups table and users.group_id

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-06-29 00:00:00.000000

Introduz o conceito de grupo (equipe) — ADR-002.

- Cria a tabela ``groups`` (id, name único, timestamps).
- Adiciona ``users.group_id`` (FK nullable para ``groups.id``).
- Semeia o grupo ``Default`` e aponta todos os usuários existentes para ele.

A migração é **aditiva e idempotente**: não toca no armazenamento vetorial (Qdrant)
nem nas memórias; apenas estende o schema relacional e faz backfill da coluna nova.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_GROUP_NAME = "Default"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) Tabela groups (idempotente).
    if "groups" not in inspector.get_table_names():
        op.create_table(
            "groups",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_groups_created_at"), "groups", ["created_at"])
        op.create_index(op.f("ix_groups_name"), "groups", ["name"], unique=True)

    # 2) Coluna users.group_id (idempotente).
    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "group_id" not in user_columns:
        op.add_column("users", sa.Column("group_id", sa.UUID(), nullable=True))
        op.create_index(op.f("ix_users_group_id"), "users", ["group_id"])
        # SQLite não suporta adicionar FK via ALTER; o alvo de produção é
        # PostgreSQL. A integridade no SQLite (testes) vem do create_all do modelo.
        if bind.dialect.name == "postgresql":
            op.create_foreign_key(
                "fk_users_group_id_groups", "users", "groups", ["group_id"], ["id"]
            )

    # 3) Seed do grupo Default + backfill dos usuários existentes.
    groups = sa.table(
        "groups",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    users = sa.table(
        "users",
        sa.column("group_id", sa.UUID()),
    )

    default_id = bind.execute(
        sa.select(groups.c.id).where(groups.c.name == DEFAULT_GROUP_NAME)
    ).scalar()
    if default_id is None:
        default_id = uuid.uuid4()
        now = sa.func.now()
        op.execute(
            groups.insert().values(
                id=default_id,
                name=DEFAULT_GROUP_NAME,
                created_at=now,
                updated_at=now,
            )
        )

    op.execute(
        users.update().where(users.c.group_id.is_(None)).values(group_id=default_id)
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "group_id" in user_columns:
        # Em SQLite a remoção de FK/coluna requer batch; o caminho de produção é
        # PostgreSQL, onde drop direto funciona.
        if bind.dialect.name == "postgresql":
            op.drop_constraint("fk_users_group_id_groups", "users", type_="foreignkey")
        op.drop_index(op.f("ix_users_group_id"), table_name="users")
        op.drop_column("users", "group_id")

    if "groups" in inspector.get_table_names():
        op.drop_index(op.f("ix_groups_name"), table_name="groups")
        op.drop_index(op.f("ix_groups_created_at"), table_name="groups")
        op.drop_table("groups")
