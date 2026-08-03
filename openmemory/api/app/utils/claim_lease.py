"""Duração do lease de um claim de TaskCard — fonte única.

Um card em ``em_andamento`` cujo ``last_activity_at`` ultrapassa esta janela é
devolvido ao backlog pelo ``SpecTaskTimeoutWorker``. Isso é intencional (evita
card abandonado travando a fila), mas antes era **invisível**: nenhum campo,
nenhum evento — o card simplesmente mudava de coluna sozinho, e quem tinha
assumido só descobria ao tentar avançar e receber ``use_claim``.

O valor mora aqui, e não no worker, porque quem responde ``claim_expires_at`` ao
cliente (task_lock / tools de leitura) precisa do MESMO número que o worker usa
para expirar. Duas cópias divergiriam no primeiro ajuste de env.

Ajustável por ``SPEC_TASK_TIMEOUT_HOURS`` (mesma env de sempre).
"""

from __future__ import annotations

import os
from datetime import timedelta

DEFAULT_TIMEOUT_HOURS = 24.0

# Ator gravado em ``TaskStatusHistory.changed_by`` pela liberação automática —
# é o que distingue expiração de ``release_task`` manual (que grava o ator
# humano). Mora aqui, e não no worker, para que o router possa reconhecê-lo ao
# montar o histórico sem depender da camada de workers.
TIMEOUT_ACTOR = "system:timeout"


def claim_timeout_hours() -> float:
    """Janela de inatividade, em horas, antes da liberação automática.

    Zero ou negativo desliga a expiração — o worker não libera nada e não há
    prazo a informar.
    """
    raw = os.getenv("SPEC_TASK_TIMEOUT_HOURS")
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_HOURS
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_HOURS


def claim_expires_at(last_activity_at):
    """Instante em que o claim expira, ou ``None`` quando não se aplica.

    ``None`` significa "sem prazo": card sem atividade registrada, ou expiração
    desligada por configuração. Nunca inventa um prazo — a ausência do campo é
    informação, não omissão.
    """
    if last_activity_at is None:
        return None
    hours = claim_timeout_hours()
    if hours <= 0:
        return None
    return last_activity_at + timedelta(hours=hours)
