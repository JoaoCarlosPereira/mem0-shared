"""add identity tables (machines, agent_tokens, link_audit_logs) and users identity columns

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-02 00:00:00.000000

Feature de autenticação Google + identidade Usuário/Máquina/Agente (ADR-004).

- Adiciona em ``users``: ``google_sub`` (único), ``display_name``, ``avatar_url``
  e ``user_type`` (``person``|``legacy_host``, default ``legacy_host``).
- Cria ``machines`` (hostname único, vínculo pessoa/legado, status).
- Cria ``agent_tokens`` (hash SHA-256 + prefixo; 1 ativo por usuário via índice
  parcial ``WHERE revoked_at IS NULL``).
- Cria ``link_audit_logs`` (trilha de vínculos/desvínculos/conflitos).
- Backfill: cada usuário existente (todos legados neste ponto) ganha uma linha
  ``machines`` com ``status='unlinked'`` e ``legacy_user_id`` preenchido.

A migração é **aditiva e idempotente**: não toca no Qdrant nem em memórias, não
altera nenhuma linha legada de ``users.user_id`` e pode ser reexecutada com
segurança (guardas via ``sa.inspect``). Enum nativo apenas no PostgreSQL, no
padrão de ``e4d5f6a7b8c9_add_partitioning_state.py``.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MACHINE_STATUS_VALUES = ("unlinked", "linked", "conflict")
_USER_TYPE_LEGACY_HOST = "legacy_host"


def _machine_status_type(is_pg: bool):
    if is_pg:
        return postgresql.ENUM(
            *_MACHINE_STATUS_VALUES, name="machinestatus", create_type=False
        )
    return sa.String()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"

    # 1) Colunas de identidade em users (idempotente).
    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "google_sub" not in user_columns:
        op.add_column("users", sa.Column("google_sub", sa.String(), nullable=True))
        op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)
    if "display_name" not in user_columns:
        op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))
    if "avatar_url" not in user_columns:
        op.add_column("users", sa.Column("avatar_url", sa.String(), nullable=True))
    if "user_type" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "user_type",
                sa.String(),
                nullable=False,
                server_default=_USER_TYPE_LEGACY_HOST,
            ),
        )
        op.create_index(op.f("ix_users_user_type"), "users", ["user_type"])

    # Backfill defensivo (server_default já cobre; garante ausência de NULL).
    users_tbl = sa.table("users", sa.column("user_type", sa.String()))
    op.execute(
        users_tbl.update()
        .where(users_tbl.c.user_type.is_(None))
        .values(user_type=_USER_TYPE_LEGACY_HOST)
    )

    # 2) Tabela machines (idempotente; enum nativo só no PostgreSQL).
    tables = set(inspector.get_table_names())
    if "machines" not in tables:
        if is_pg:
            postgresql.ENUM(*_MACHINE_STATUS_VALUES, name="machinestatus").create(
                bind, checkfirst=True
            )
        op.create_table(
            "machines",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("hostname", sa.String(), nullable=False),
            sa.Column("linked_user_id", sa.UUID(), nullable=True),
            sa.Column("legacy_user_id", sa.UUID(), nullable=True),
            sa.Column(
                "status",
                _machine_status_type(is_pg),
                nullable=False,
                server_default="unlinked",
            ),
            sa.Column("linked_at", sa.DateTime(), nullable=True),
            sa.Column("linked_by", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_machines_hostname"), "machines", ["hostname"], unique=True)
        op.create_index(op.f("ix_machines_linked_user_id"), "machines", ["linked_user_id"])
        op.create_index(op.f("ix_machines_legacy_user_id"), "machines", ["legacy_user_id"])
        op.create_index(op.f("ix_machines_status"), "machines", ["status"])
        op.create_index(op.f("ix_machines_created_at"), "machines", ["created_at"])
        if is_pg:
            op.create_foreign_key(
                "fk_machines_linked_user_id_users",
                "machines", "users", ["linked_user_id"], ["id"],
            )
            op.create_foreign_key(
                "fk_machines_legacy_user_id_users",
                "machines", "users", ["legacy_user_id"], ["id"],
            )
            op.create_foreign_key(
                "fk_machines_linked_by_users",
                "machines", "users", ["linked_by"], ["id"],
            )

    # 3) Tabela agent_tokens (idempotente) + índice parcial de 1 ativo/usuário.
    if "agent_tokens" not in tables:
        op.create_table(
            "agent_tokens",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("prefix", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_agent_tokens_user_id"), "agent_tokens", ["user_id"])
        op.create_index(op.f("ix_agent_tokens_token_hash"), "agent_tokens", ["token_hash"])
        op.create_index(op.f("ix_agent_tokens_created_at"), "agent_tokens", ["created_at"])
        op.create_index(
            "uq_agent_tokens_active_user",
            "agent_tokens",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("revoked_at IS NULL"),
            sqlite_where=sa.text("revoked_at IS NULL"),
        )
        if is_pg:
            op.create_foreign_key(
                "fk_agent_tokens_user_id_users",
                "agent_tokens", "users", ["user_id"], ["id"],
            )

    # 4) Tabela link_audit_logs (idempotente).
    if "link_audit_logs" not in tables:
        op.create_table(
            "link_audit_logs",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("machine_id", sa.UUID(), nullable=False),
            sa.Column("actor_user_id", sa.UUID(), nullable=True),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("detail", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_link_audit_logs_machine_id"), "link_audit_logs", ["machine_id"])
        op.create_index(op.f("ix_link_audit_logs_actor_user_id"), "link_audit_logs", ["actor_user_id"])
        op.create_index(op.f("ix_link_audit_logs_action"), "link_audit_logs", ["action"])
        op.create_index(op.f("ix_link_audit_logs_created_at"), "link_audit_logs", ["created_at"])
        if is_pg:
            op.create_foreign_key(
                "fk_link_audit_logs_machine_id_machines",
                "link_audit_logs", "machines", ["machine_id"], ["id"],
            )
            op.create_foreign_key(
                "fk_link_audit_logs_actor_user_id_users",
                "link_audit_logs", "users", ["actor_user_id"], ["id"],
            )

    # 5) Backfill: uma linha machines 'unlinked' por usuário existente cujo
    #    hostname ainda não está catalogado (idempotente por diferença).
    users_src = sa.table(
        "users",
        sa.column("id", sa.UUID()),
        sa.column("user_id", sa.String()),
    )
    machines_tbl = sa.table(
        "machines",
        sa.column("id", sa.UUID()),
        sa.column("hostname", sa.String()),
        sa.column("legacy_user_id", sa.UUID()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    existing_hostnames = {
        row[0] for row in bind.execute(sa.select(machines_tbl.c.hostname))
    }
    now = sa.func.now()
    for user_pk, hostname in bind.execute(
        sa.select(users_src.c.id, users_src.c.user_id)
    ):
        if hostname in existing_hostnames:
            continue
        op.execute(
            machines_tbl.insert().values(
                id=uuid.uuid4(),
                hostname=hostname,
                legacy_user_id=user_pk,
                status="unlinked",
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    tables = set(inspector.get_table_names())

    if "link_audit_logs" in tables:
        op.drop_table("link_audit_logs")
    if "agent_tokens" in tables:
        op.drop_table("agent_tokens")
    if "machines" in tables:
        op.drop_table("machines")
    if is_pg:
        postgresql.ENUM(name="machinestatus").drop(bind, checkfirst=True)

    user_columns = {c["name"] for c in inspector.get_columns("users")}
    if "user_type" in user_columns:
        op.drop_index(op.f("ix_users_user_type"), table_name="users")
        op.drop_column("users", "user_type")
    if "avatar_url" in user_columns:
        op.drop_column("users", "avatar_url")
    if "display_name" in user_columns:
        op.drop_column("users", "display_name")
    if "google_sub" in user_columns:
        op.drop_index(op.f("ix_users_google_sub"), table_name="users")
        op.drop_column("users", "google_sub")
