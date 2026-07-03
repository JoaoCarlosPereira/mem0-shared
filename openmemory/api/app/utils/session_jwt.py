"""Emissão e validação do JWT de sessão da UI (feature auth Google, ADR-002).

A API é a fonte da verdade de identidade: após validar o ID token do Google,
emite este JWT próprio (HS256, ``AUTH_JWT_SECRET``) que a UI anexa como Bearer
em todas as chamadas. O TTL deve ficar alinhado ao da sessão NextAuth
(``AUTH_JWT_TTL_SECONDS``, default 7 dias).
"""

import datetime
import os

import jwt

ALGORITHM = "HS256"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 dias, alinhado ao default do NextAuth


class SessionJwtError(Exception):
    """Falha de configuração, assinatura ou expiração do JWT de sessão."""


def _secret() -> str:
    secret = os.getenv("AUTH_JWT_SECRET", "").strip()
    if not secret:
        # Fail-closed: sem segredo configurado não há emissão nem validação.
        raise SessionJwtError("AUTH_JWT_SECRET não configurado")
    return secret


def issue_session_jwt(*, user_id, email: str = "", name: str = "") -> str:
    """Emite o JWT de sessão para uma pessoa autenticada."""
    ttl = int(os.getenv("AUTH_JWT_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)))
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user_id),
        "email": email or "",
        "name": name or "",
        "iat": now,
        "exp": now + datetime.timedelta(seconds=ttl),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_session_jwt(token: str) -> dict:
    """Decodifica e valida o JWT de sessão; levanta ``SessionJwtError`` se inválido."""
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise SessionJwtError(str(exc)) from exc
