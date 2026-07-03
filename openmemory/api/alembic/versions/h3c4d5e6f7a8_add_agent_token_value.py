"""add agent_tokens.token_value (token imutável e exibível — ADR-008)

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-07-03 00:00:00.000000

Decisão de produto (ADR-008): o token de agente é gerado uma única vez por
conta, é imutável e fica permanentemente visível na tela de instalação. Para
isso o valor em claro passa a ser armazenado (``token_value``) ao lado do hash
(que continua sendo o índice de autenticação do middleware). Aditiva e
idempotente; linhas antigas (se existirem) ficam com ``token_value`` NULL.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h3c4d5e6f7a8"
down_revision: Union[str, None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("agent_tokens")}
    if "token_value" not in columns:
        op.add_column(
            "agent_tokens", sa.Column("token_value", sa.String(), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("agent_tokens")}
    if "token_value" in columns:
        op.drop_column("agent_tokens", "token_value")
