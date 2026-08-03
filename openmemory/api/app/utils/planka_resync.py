"""Bootstrap / resync Spec → PLANKA mirror (idempotent via id_map).

Never deletes Spec data. Spec remains SoT (ADR-005 / ADR-003).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import SpecDocument, SpecPlankaIdMap, SpecWorkspace, TaskCard
from app.utils.planka import (
    ENTITY_BOARD,
    ENTITY_DOCUMENT,
    ENTITY_TASK,
    PlankaMirrorError,
    PlankaMirrorHttpClient,
)


@dataclass
class WorkspaceResyncResult:
    workspace_id: str
    board_id: Optional[str] = None
    spec_tasks: int = 0
    mirrored_tasks: int = 0
    spec_documents: int = 0
    mirrored_documents: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResyncReport:
    workspaces: list[WorkspaceResyncResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def resync_workspace(
    db: Session,
    workspace_id: UUID,
    *,
    client: Optional[PlankaMirrorHttpClient] = None,
) -> WorkspaceResyncResult:
    """Mirror one SpecWorkspace onto PLANKA. Idempotent."""
    result = WorkspaceResyncResult(workspace_id=str(workspace_id))
    workspace = db.query(SpecWorkspace).filter(SpecWorkspace.id == workspace_id).first()
    if not workspace:
        result.errors.append(f"workspace {workspace_id} não encontrado")
        return result

    mirror = client or PlankaMirrorHttpClient(db)
    try:
        board_id = await mirror.ensure_workspace_board(workspace_id)
        result.board_id = board_id
    except PlankaMirrorError as exc:
        result.errors.append(f"ensure_workspace_board: {exc.detail}")
        return result

    tasks = db.query(TaskCard).filter(TaskCard.workspace_id == workspace_id).all()
    result.spec_tasks = len(tasks)
    for task in tasks:
        try:
            await mirror.mirror_task(task.id)
            result.mirrored_tasks += 1
        except PlankaMirrorError as exc:
            result.errors.append(f"task {task.id}: {exc.detail}")

    documents = db.query(SpecDocument).filter(SpecDocument.workspace_id == workspace_id).all()
    result.spec_documents = len(documents)
    for document in documents:
        try:
            await mirror.mirror_document(workspace_id, document.document_type.value)
            result.mirrored_documents += 1
        except PlankaMirrorError as exc:
            result.errors.append(f"document {document.document_type.value}: {exc.detail}")

    return result


async def resync_all(
    db: Session,
    *,
    client: Optional[PlankaMirrorHttpClient] = None,
) -> dict[str, Any]:
    """Mirror every SpecWorkspace. Never deletes Spec rows."""
    report = ResyncReport()
    workspaces = db.query(SpecWorkspace).order_by(SpecWorkspace.created_at.asc()).all()
    mirror = client or PlankaMirrorHttpClient(db)
    for workspace in workspaces:
        result = await resync_workspace(db, workspace.id, client=mirror)
        report.workspaces.append(result)
        report.errors.extend(result.errors)

    workspace_ids = [w.id for w in workspaces]
    payload = {
        "workspaces": [w.to_dict() for w in report.workspaces],
        "errors": list(report.errors),
        "totals": {
            "workspaces": len(report.workspaces),
            "spec_tasks": sum(w.spec_tasks for w in report.workspaces),
            "mirrored_tasks": sum(w.mirrored_tasks for w in report.workspaces),
            "spec_documents": sum(w.spec_documents for w in report.workspaces),
            "mirrored_documents": sum(w.mirrored_documents for w in report.workspaces),
            "planka_boards_mapped": (
                db.query(SpecPlankaIdMap)
                .filter(
                    SpecPlankaIdMap.entity_type == ENTITY_BOARD,
                    SpecPlankaIdMap.spec_id.in_(workspace_ids) if workspace_ids else False,
                )
                .count()
                if workspace_ids
                else 0
            ),
            "planka_tasks_mapped": (
                db.query(SpecPlankaIdMap).filter(SpecPlankaIdMap.entity_type == ENTITY_TASK).count()
            ),
            "planka_documents_mapped": (
                db.query(SpecPlankaIdMap)
                .filter(SpecPlankaIdMap.entity_type == ENTITY_DOCUMENT)
                .count()
            ),
        },
    }
    return payload
