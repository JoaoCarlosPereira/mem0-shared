"""Identidade do sujeito de AccessControl / ator de specs.

Nunca confiar em ``subject_id`` / ``claimant`` vindos do cliente para ACL: o
sujeito vem de ``auth_user_var`` (session JWT ou agent token). Sem identidade
autenticada, ``subject_id=None`` preserva o comportamento aberto por padrão
(sem regras → todos os workspaces), igual às memórias em modo legado.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from app.utils.identity import resolve_hostname
from app.utils.logging_context import (
    auth_email_var,
    auth_method_var,
    auth_user_var,
    machine_var,
)


def resolve_spec_subject() -> tuple[str, Optional[UUID]]:
    """``(subject_type, subject_id)`` a partir do contexto de autenticação."""
    raw = (auth_user_var.get() or "").strip()
    if not raw:
        return "user", None
    try:
        return "user", UUID(raw)
    except ValueError:
        return "user", None


def resolve_spec_actor(
    *,
    body_actor: Optional[str] = None,
    db: Any | None = None,
) -> Optional[str]:
    """Hostname / ator para claim, audit e versionamento.

    Preferência: máquina vinculada ao agent token → pessoa da sessão →
    ``body_actor`` (UI legada) → None.
    """
    bound = (machine_var.get() or "").strip()
    if auth_method_var.get() == "agent_token" and bound:
        return resolve_hostname(bound)
    if auth_method_var.get() == "session":
        raw_user_id = (auth_user_var.get() or "").strip()
        if db is not None and raw_user_id:
            try:
                from app.models import User

                user = db.query(User).filter(User.id == UUID(raw_user_id)).first()
                if user is not None:
                    actor = (user.display_name or user.name or user.email or "").strip()
                    if actor:
                        return actor
            except (TypeError, ValueError):
                pass
        email = (auth_email_var.get() or "").strip()
        if email:
            return email
    if body_actor and str(body_actor).strip():
        return resolve_hostname(str(body_actor).strip())
    return None
