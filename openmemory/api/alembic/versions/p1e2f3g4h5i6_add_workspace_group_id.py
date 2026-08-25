"""add workspace group_id (isolation por grupo)

Revision ID: p1e2f3g4h5i6
Revises: o0d1e2f3g4h5
Create Date: 2026-08-22 00:00:00.000000

Tarefa kanban-board-group-isolation. Adiciona a coluna ``group_id`` em
``spec_workspaces`` (FK para ``groups.id``, indexada, nullable) para que o
donos de cada quadro Kanban seja metadado **imutavel** e resolvido no momento
da criacao.

Backfill dos workspaces legados (fail-closed): resolve ``created_by`` contra as
identidades de usuario confiaveis e copia o ``group_id`` ATUAL do criador.

- Caminho 1 (hostname/usuario legado): ``created_by`` == ``users.user_id``
  (case-insensitive), incluindo variantes de casing catalogadas em ``machines``.
- Caminho 2 (e-mail sem ambiguidade): ``created_by`` == ``users.email`` quando
  exatamente uma pessoa possui aquele e-mail.

Linhas ambiguas (mais de um candidato), sem correspondencia, ou com criador
sem grupo permanecem com ``group_id = NULL`` (fail-closed) e NUNCA sao
atribuidas ao grupo ``Default``.

A migracao e **aditiva, idempotente e portavel** (PostgreSQL e SQLite): o FK
so e criado no PostgreSQL (SQLite nao suporta ``ALTER ... ADD CONSTRAINT``),
mesmo padrao de ``g2b3c4d5e6f7_add_identity_tables.py``. O backfill usa
iteracao em Python para funcionar nos dois dialetos.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p1e2f3g4h5i6"
down_revision: Union[str, None] = "o0d1e2f3g4h5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_WS = "spec_workspaces"
_FK = "fk_spec_workspaces_group_id"
_IDX = "ix_spec_workspaces_group_id"


def _backfill_workspace_groups(bind) -> None:
    """Copia o ``group_id`` atual do criador para workspaces ainda sem grupo."""
    users = bind.execute(
        sa.text(
            "SELECT id, user_id, email, group_id FROM users WHERE group_id IS NOT NULL"
        )
    ).fetchall()
    machines = bind.execute(
        sa.text("SELECT hostname, legacy_user_id FROM machines WHERE legacy_user_id IS NOT NULL")
    ).fetchall()

    # hostname -> group_id (agregando duplicatas de casing via machines + users)
    host_to_group: dict[str, list] = {}
    email_to_group: dict[str, list] = {}
    for _uid, user_id, email, gid in users:
        if user_id:
            host_to_group.setdefault(str(user_id).strip().lower(), []).append(gid)
        if email:
            email_to_group.setdefault(str(email).strip().lower(), []).append(gid)
    for hostname, legacy_user_id in machines:
        if not hostname:
            continue
        g = host_to_group.get(str(hostname).strip().lower())
        if g:
            for gid in g:
                if gid not in host_to_group.setdefault(hostname.strip().lower(), []):
                    host_to_group[hostname.strip().lower()].append(gid)

    rows = bind.execute(
        sa.text(f"SELECT id, created_by FROM {_WS} WHERE group_id IS NULL AND created_by IS NOT NULL")
    ).fetchall()

    for ws_id, created_by in rows:
        if not created_by:
            continue
        key = str(created_by).strip().lower()
        # Caminho 1: hostname/usuario legado (unica correspondencia).
        gids = host_to_group.get(key)
        resolved = None
        if gids:
            unique = set(gids)
            if len(unique) == 1:
                resolved = unique.pop()
        # Caminho 2: e-mail sem ambiguidade.
        if resolved is None:
            egids = email_to_group.get(key)
            if egids:
                unique = set(egids)
                if len(unique) == 1:
                    resolved = unique.pop()
        if resolved is not None:
            bind.execute(
                sa.text(f"UPDATE {_WS} SET group_id = :g WHERE id = :id AND group_id IS NULL"),
                {"g": resolved, "id": ws_id},
            )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    tables = set(inspector.get_table_names())

    if _WS not in tables:
        return

    cols = {c["name"] for c in inspector.get_columns(_WS)}
    if "group_id" not in cols:
        op.add_column(_WS, sa.Column("group_id", sa.UUID(), nullable=True))
        op.create_index(_IDX, _WS, ["group_id"])
        if is_pg:
            op.create_foreign_key(_FK, _WS, "groups", ["group_id"], ["id"])

        _backfill_workspace_groups(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    is_pg = bind.dialect.name == "postgresql"
    if _WS in set(inspector.get_table_names()):
        cols = {c["name"] for c in inspector.get_columns(_WS)}
        if "group_id" in cols:
            if is_pg:
                op.drop_constraint(_FK, _WS, type_="foreignkey")
            op.drop_index(_IDX, table_name=_WS)
            op.drop_column(_WS, "group_id")
