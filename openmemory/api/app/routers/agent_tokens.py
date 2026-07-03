"""Token de agente do usuário autenticado (ADR-003/ADR-008).

Modelo imutável (decisão de produto — ADR-008): o token é criado UMA vez por
conta (get-or-create idempotente) e o valor em claro fica permanentemente
recuperável para a tela de instalação. Não há rotação nem revogação via API —
``revoked_at`` é válvula administrativa (UPDATE direto no banco) e continua
honrada pelo middleware. Gestão exige sessão da UI (JWT); credenciais de
agente/equipe não gerenciam tokens.
"""

import datetime
from typing import Optional

from app.database import get_db
from app.models import AgentToken, User
from app.routers.auth import require_session_person
from app.utils.agent_tokens import generate_token, hash_token
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/agent-token", tags=["agent-token"])


class TokenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token: Optional[str] = None  # valor em claro (exibição permanente, ADR-008)
    prefix: str
    created_at: Optional[datetime.datetime] = None
    last_used_at: Optional[datetime.datetime] = None


def _active_token(db: Session, user: User) -> Optional[AgentToken]:
    return (
        db.query(AgentToken)
        .filter(AgentToken.user_id == user.id, AgentToken.revoked_at.is_(None))
        .first()
    )


def _to_response(row: AgentToken) -> TokenResponse:
    return TokenResponse(
        token=row.token_value,
        prefix=row.prefix,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
    )


@router.post("", response_model=TokenResponse)
def get_or_create_token(
    user: User = Depends(require_session_person),
    db: Session = Depends(get_db),
):
    """Idempotente: cria o token da conta na 1ª chamada; depois devolve o mesmo.

    Nunca rotaciona (token imutável — ADR-008).
    """
    current = _active_token(db, user)
    if current is not None:
        return _to_response(current)

    raw, prefix = generate_token()
    row = AgentToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        token_value=raw,
        prefix=prefix,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.get("", response_model=TokenResponse)
def get_token(
    user: User = Depends(require_session_person),
    db: Session = Depends(get_db),
):
    """Token ativo da conta (com o valor — exibição permanente) ou 404."""
    current = _active_token(db, user)
    if current is None:
        raise HTTPException(status_code=404, detail="nenhum token gerado")
    return _to_response(current)
