"""Validação de hostname de máquina (padrão Sysmo: S + 4 dígitos)."""

from __future__ import annotations

import re

# Ex.: S0281, S0293 — evita textos como "S0281 - Ana Paula" no onboarding.
SYSMO_HOSTNAME_RE = re.compile(r"^S\d{4}$", re.IGNORECASE)

SYSMO_HOSTNAME_MESSAGE = (
    "Hostname inválido: use o código da máquina no formato S + 4 dígitos (ex.: S0281)."
)


def normalize_sysmo_hostname(raw: str) -> str | None:
    """Retorna o hostname normalizado (maiúsculas) ou ``None`` se inválido."""
    trimmed = (raw or "").strip()
    if not SYSMO_HOSTNAME_RE.match(trimmed):
        return None
    return trimmed.upper()


def require_sysmo_hostname(raw: str) -> str:
    """Valida e normaliza; levanta ``ValueError`` com mensagem amigável."""
    normalized = normalize_sysmo_hostname(raw)
    if normalized is None:
        raise ValueError(SYSMO_HOSTNAME_MESSAGE)
    return normalized
