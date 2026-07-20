"""Exclusividade de claim e mudança de status de tasks (ADR-003/ADR-005/ADR-007).

Lógica de domínio pura (recebe ``db: Session``, sem FastAPI ``Request``/
``Response``) reaproveitada pelo router REST (Tarefa 4), pelas tools MCP
(Tarefa 8) e pelo job de liberação por timeout (Tarefa 5). Toda operação usa a
mesma primitiva de concorrência otimista dos documentos: um
``UPDATE ... WHERE id = :id AND <guarda>`` atômico cujo ``rowcount == 0`` sinaliza
que a task já estava em outro estado (reivindicada ou em outra versão).
"""

import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import (
    SpecAuditLog,
    TaskCard,
    TaskCardStatus,
    TaskStatusHistory,
    get_current_utc_time,
)


@dataclass
class ClaimTaskResult:
    """Resultado de ``claim_task``/``release_task`` (ver TechSpec — Interfaces)."""
    claimed: bool
    current_assignee: str | None
    version: int


@dataclass
class UpdateTaskStatusResult:
    """Resultado de ``update_task_status`` (ClaimTaskResult-like, com conflito)."""
    updated: bool
    conflict: bool
    version: int
    status: str
    current_assignee: str | None


def _coerce_status(status: TaskCardStatus | str) -> TaskCardStatus:
    return status if isinstance(status, TaskCardStatus) else TaskCardStatus(status)


def claim_task(db: Session, task_id: uuid.UUID, claimant: str) -> ClaimTaskResult:
    """Reivindica uma task disponível (coluna ``tasks``), movendo-a para ``em_andamento``.

    Falha (``claimed=False``), sem alterar o registro, se a task não estiver na
    coluna ``tasks`` — o que inclui o caso de já estar ``em_andamento`` com outro
    ``assignee``. Retorna o ``assignee`` vigente para o chamador reconciliar.
    """
    task = db.get(TaskCard, task_id)
    if task is None:
        raise ValueError(f"TaskCard {task_id} não encontrada")

    now = get_current_utc_time()
    result = db.execute(
        sa.update(TaskCard)
        .where(
            TaskCard.id == task_id,
            TaskCard.status == TaskCardStatus.tasks,
        )
        .values(
            assignee=claimant,
            status=TaskCardStatus.em_andamento,
            version=TaskCard.version + 1,
            last_activity_at=now,
            updated_at=now,
        )
    )

    if result.rowcount == 0:
        db.rollback()
        fresh = db.get(TaskCard, task_id)
        return ClaimTaskResult(
            claimed=False,
            current_assignee=fresh.assignee,
            version=fresh.version,
        )

    db.add(
        TaskStatusHistory(
            task_id=task_id,
            old_status=TaskCardStatus.tasks,
            new_status=TaskCardStatus.em_andamento,
            changed_by=claimant,
        )
    )
    db.add(
        SpecAuditLog(
            workspace_id=task.workspace_id,
            actor=claimant,
            action="claim_task",
            detail={"task_id": str(task_id)},
        )
    )
    db.commit()

    fresh = db.get(TaskCard, task_id)
    return ClaimTaskResult(
        claimed=True,
        current_assignee=claimant,
        version=fresh.version,
    )


def release_task(
    db: Session,
    task_id: uuid.UUID,
    actor: str | None,
    reason: str | None = None,
) -> ClaimTaskResult:
    """Libera uma task manualmente (ou via job de timeout — Tarefa 5).

    Volta o status para ``tasks``, limpa ``assignee`` e o marcador de bloqueio
    (``is_blocked``/``block_reason``) e registra ``TaskStatusHistory``. Bump de
    ``version`` invalida qualquer gravação otimista em voo. Idempotente em
    efeito: liberar uma task já em ``tasks`` apenas reafirma o estado.
    """
    task = db.get(TaskCard, task_id)
    if task is None:
        raise ValueError(f"TaskCard {task_id} não encontrada")

    old_status = task.status
    now = get_current_utc_time()

    task.status = TaskCardStatus.tasks
    task.assignee = None
    task.is_blocked = False
    task.block_reason = None
    task.version = task.version + 1
    task.last_activity_at = now
    task.updated_at = now

    db.add(
        TaskStatusHistory(
            task_id=task_id,
            old_status=old_status,
            new_status=TaskCardStatus.tasks,
            changed_by=actor,
        )
    )
    db.add(
        SpecAuditLog(
            workspace_id=task.workspace_id,
            actor=actor,
            action="release_task",
            detail={"reason": reason} if reason else {},
        )
    )
    db.commit()
    db.refresh(task)

    return ClaimTaskResult(
        claimed=False,
        current_assignee=None,
        version=task.version,
    )


def update_task_status(
    db: Session,
    task_id: uuid.UUID,
    new_status: TaskCardStatus | str,
    expected_version: int,
    actor: str | None,
    is_blocked: bool | None = None,
    block_reason: str | None = None,
) -> UpdateTaskStatusResult:
    """Muda o status (coluna) de uma task com concorrência otimista.

    ``expected_version`` desatualizado retorna ``conflict=True`` sem alterar
    nada. ``is_blocked``/``block_reason`` são opcionais e ortogonais à coluna —
    reportar bloqueio = chamar com ``new_status`` igual ao atual e
    ``is_blocked=True`` (ver ADR-007). Registra ``TaskStatusHistory`` na mudança.
    """
    new_status = _coerce_status(new_status)

    task = db.get(TaskCard, task_id)
    if task is None:
        raise ValueError(f"TaskCard {task_id} não encontrada")

    old_status = task.status
    now = get_current_utc_time()

    values = {
        "status": new_status,
        "version": TaskCard.version + 1,
        "last_activity_at": now,
        "updated_at": now,
    }
    if is_blocked is not None:
        values["is_blocked"] = is_blocked
        values["block_reason"] = block_reason

    result = db.execute(
        sa.update(TaskCard)
        .where(
            TaskCard.id == task_id,
            TaskCard.version == expected_version,
        )
        .values(**values)
    )

    if result.rowcount == 0:
        db.rollback()
        fresh = db.get(TaskCard, task_id)
        return UpdateTaskStatusResult(
            updated=False,
            conflict=True,
            version=fresh.version,
            status=fresh.status.value,
            current_assignee=fresh.assignee,
        )

    if new_status != old_status:
        db.add(
            TaskStatusHistory(
                task_id=task_id,
                old_status=old_status,
                new_status=new_status,
                changed_by=actor,
            )
        )
    db.add(
        SpecAuditLog(
            workspace_id=task.workspace_id,
            actor=actor,
            action="update_task_status",
            detail={
                "old_status": old_status.value,
                "new_status": new_status.value,
                "is_blocked": is_blocked,
            },
        )
    )
    db.commit()

    fresh = db.get(TaskCard, task_id)
    return UpdateTaskStatusResult(
        updated=True,
        conflict=False,
        version=fresh.version,
        status=fresh.status.value,
        current_assignee=fresh.assignee,
    )
