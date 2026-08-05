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
from app.utils.claim_lease import claim_expires_at
from app.utils.kanban_pipeline import KanbanSkipError, assert_no_forward_skip


@dataclass
class ClaimTaskResult:
    """Resultado de ``claim_task``/``release_task`` (ver TechSpec — Interfaces).

    ``expires_at`` é o prazo do lease do claim (ver ``app.utils.claim_lease``);
    ``None`` quando não se aplica — release, falha de claim ou expiração desligada.
    """
    claimed: bool
    current_assignee: str | None
    version: int
    expires_at: object | None = None


@dataclass
class UpdateTaskStatusResult:
    """Resultado de ``update_task_status`` (ClaimTaskResult-like, com conflito)."""
    updated: bool
    conflict: bool
    version: int
    status: str
    current_assignee: str | None


@dataclass
class UpdateTaskMetadataResult:
    """Resultado de ``update_task_metadata`` (concorrência otimista atômica)."""
    updated: bool
    conflict: bool
    version: int
    title: str
    description: str | None
    branch_ref: str | None
    due_at: object | None = None
    position: float | None = None


class TaskStatusPolicyError(ValueError):
    """Transição de status inválida (use claim/release; exclusividade ADR-003)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _coerce_status(status: TaskCardStatus | str) -> TaskCardStatus:
    return status if isinstance(status, TaskCardStatus) else TaskCardStatus(status)


def _assert_status_policy(
    task: TaskCard,
    new_status: TaskCardStatus,
    actor: str | None,
) -> None:
    """Garante exclusividade de claim: em_andamento só via claim; backlog só via release."""
    old_status = task.status
    if old_status == TaskCardStatus.tasks and new_status != TaskCardStatus.tasks:
        raise TaskStatusPolicyError(
            "use_claim",
            "Use claim_task para sair do backlog (tasks)",
        )
    if (
        new_status == TaskCardStatus.em_andamento
        and old_status != TaskCardStatus.em_andamento
    ):
        raise TaskStatusPolicyError(
            "use_claim",
            "Use claim_task para entrar em em_andamento",
        )
    if new_status == TaskCardStatus.tasks and old_status != TaskCardStatus.tasks:
        raise TaskStatusPolicyError(
            "use_release",
            "Use release_task para devolver a task ao backlog",
        )
    if task.assignee and (not actor or actor != task.assignee):
        raise TaskStatusPolicyError(
            "not_assignee",
            f"Apenas o assignee ({task.assignee}) pode alterar o status",
        )
    try:
        assert_no_forward_skip(old_status, new_status)
    except KanbanSkipError as exc:
        raise TaskStatusPolicyError(exc.code, exc.message) from exc


def claim_task(db: Session, task_id: uuid.UUID, claimant: str) -> ClaimTaskResult:
    """Reivindica uma task, movendo-a para ``em_andamento``.

    Dois caminhos, ambos terminando em ``em_andamento`` com o chamador como
    assignee:

    1. **Task livre** (coluna ``tasks``): claim normal.
    2. **Task que já é do chamador**, em qualquer coluna: idempotente. Reassume o
       card e renova o lease. É o que permite (a) devolver a ``em_andamento`` um
       card cuja verificação reprovou em ``revisao_codigo``/``fase_teste`` — o
       fluxo que o próprio bloco ``kanban`` instrui — e (b) renovar um claim antes
       que o timeout o devolva ao backlog. Antes, ambos eram impossíveis: o
       ``UPDATE`` exigia ``status == tasks``, então o assignee recebia
       ``claimed: false`` apontando ele mesmo como "outro responsável", e as
       únicas saídas eram ``release_task`` (que perde a atribuição e faz o card
       parecer abandonado) ou mentir sobre a coluna com ``is_blocked``.

    Falha (``claimed=False``) apenas quando a task está ativa com assignee
    DIFERENTE — a exclusividade para terceiros continua intacta. Retorna o
    ``assignee`` vigente para o chamador reconciliar.
    """
    task = db.get(TaskCard, task_id)
    if task is None:
        raise ValueError(f"TaskCard {task_id} não encontrada")

    now = get_current_utc_time()
    old_status = task.status
    # Reassunção do próprio card: qualquer coluna serve como origem, desde que o
    # assignee gravado seja o chamador. A guarda vai no WHERE (não num if sobre o
    # objeto lido) para manter a atomicidade — entre o SELECT e o UPDATE outro
    # processo pode ter liberado ou reatribuído a task.
    is_reclaim = task.assignee == claimant and old_status != TaskCardStatus.tasks
    if is_reclaim:
        guard = sa.and_(
            TaskCard.id == task_id,
            TaskCard.assignee == claimant,
        )
    else:
        guard = sa.and_(
            TaskCard.id == task_id,
            TaskCard.status == TaskCardStatus.tasks,
        )

    result = db.execute(
        sa.update(TaskCard)
        .where(guard)
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

    if old_status != TaskCardStatus.em_andamento:
        db.add(
            TaskStatusHistory(
                task_id=task_id,
                old_status=old_status,
                new_status=TaskCardStatus.em_andamento,
                changed_by=claimant,
            )
        )
    db.add(
        SpecAuditLog(
            workspace_id=task.workspace_id,
            actor=claimant,
            action="reclaim_task" if is_reclaim else "claim_task",
            detail={"task_id": str(task_id), "from_status": old_status.value},
        )
    )
    db.commit()

    fresh = db.get(TaskCard, task_id)
    # Spec → PLANKA sync (no-op unless PLANKA_MIRROR_SYNC enabled).
    from app.utils.planka_hooks import mirror_task_status

    mirror_task_status(db, task_id)
    return ClaimTaskResult(
        claimed=True,
        current_assignee=claimant,
        version=fresh.version,
        expires_at=claim_expires_at(fresh.last_activity_at),
    )


def release_task(
    db: Session,
    task_id: uuid.UUID,
    actor: str | None,
    reason: str | None = None,
    expected_version: int | None = None,
) -> ClaimTaskResult:
    """Libera uma task manualmente (ou via job de timeout — Tarefa 5).

    Volta o status para ``tasks``, limpa ``assignee`` e o marcador de bloqueio
    (``is_blocked``/``block_reason``) e registra ``TaskStatusHistory``. Bump de
    ``version`` invalida qualquer gravação otimista em voo.

    ``expected_version``:
    - ``None`` (release manual): incondicional — sempre aplica. ``claimed=False``.
    - inteiro (job de timeout): usa ``UPDATE ... WHERE version = :expected`` para
      ser idempotente entre réplicas — só uma consegue liberar. ``claimed=True``
      quando ESTA chamada aplicou a liberação; ``claimed=False`` quando outra
      réplica já a fez (no-op).
    """
    task = db.get(TaskCard, task_id)
    if task is None:
        raise ValueError(f"TaskCard {task_id} não encontrada")

    old_status = task.status
    now = get_current_utc_time()

    if expected_version is not None:
        result = db.execute(
            sa.update(TaskCard)
            .where(
                TaskCard.id == task_id,
                TaskCard.version == expected_version,
                TaskCard.status == TaskCardStatus.em_andamento,
            )
            .values(
                status=TaskCardStatus.tasks,
                assignee=None,
                is_blocked=False,
                block_reason=None,
                version=TaskCard.version + 1,
                last_activity_at=now,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            # Outra réplica já liberou (ou a versão mudou): no-op idempotente.
            db.rollback()
            fresh = db.get(TaskCard, task_id)
            return ClaimTaskResult(
                claimed=False,
                current_assignee=fresh.assignee,
                version=fresh.version,
            )
        applied = True
    else:
        task.status = TaskCardStatus.tasks
        task.assignee = None
        task.is_blocked = False
        task.block_reason = None
        task.version = task.version + 1
        task.last_activity_at = now
        task.updated_at = now
        applied = False  # release manual não é um "claim"

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
    fresh = db.get(TaskCard, task_id)

    from app.utils.planka_hooks import mirror_task_status

    mirror_task_status(db, task_id)
    return ClaimTaskResult(
        claimed=applied,
        current_assignee=None,
        version=fresh.version,
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

    _assert_status_policy(task, new_status, actor)

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
    from app.utils.workspace_lifecycle import reconcile_workspace_completion_from_tasks

    reconcile_workspace_completion_from_tasks(
        db,
        fresh.workspace_id,
        actor=actor or "kanban-auto",
    )
    from app.utils.planka_hooks import mirror_task_status

    mirror_task_status(db, task_id)
    return UpdateTaskStatusResult(
        updated=True,
        conflict=False,
        version=fresh.version,
        status=fresh.status.value,
        current_assignee=fresh.assignee,
    )


def update_task_metadata(
    db: Session,
    task_id: uuid.UUID,
    expected_version: int,
    *,
    title: str | None = None,
    description: str | None = None,
    branch_ref: str | None = None,
    due_at: object | None = ...,
    position: float | None = None,
    clear_due_at: bool = False,
) -> UpdateTaskMetadataResult:
    """Atualiza metadados com ``UPDATE … WHERE version = :expected`` atômico.

    Também renova ``last_activity_at`` para que edições contem como atividade
    perante o timeout worker. ``due_at`` usa sentinel ``...`` para "não alterar";
    ``clear_due_at=True`` zera o prazo.
    """
    task = db.get(TaskCard, task_id)
    if task is None:
        raise ValueError(f"TaskCard {task_id} não encontrada")

    now = get_current_utc_time()
    values: dict = {
        "version": TaskCard.version + 1,
        "last_activity_at": now,
        "updated_at": now,
    }
    if title is not None:
        values["title"] = title
    if description is not None:
        values["description"] = description
    if branch_ref is not None:
        values["branch_ref"] = branch_ref
    if clear_due_at:
        values["due_at"] = None
    elif due_at is not ...:
        values["due_at"] = due_at
    if position is not None:
        values["position"] = position

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
        return UpdateTaskMetadataResult(
            updated=False,
            conflict=True,
            version=fresh.version,
            title=fresh.title,
            description=fresh.description,
            branch_ref=fresh.branch_ref,
            due_at=fresh.due_at,
            position=fresh.position,
        )

    db.commit()
    fresh = db.get(TaskCard, task_id)
    from app.utils.planka_hooks import mirror_task

    mirror_task(db, task_id)
    return UpdateTaskMetadataResult(
        updated=True,
        conflict=False,
        version=fresh.version,
        title=fresh.title,
        description=fresh.description,
        branch_ref=fresh.branch_ref,
        due_at=fresh.due_at,
        position=fresh.position,
    )
