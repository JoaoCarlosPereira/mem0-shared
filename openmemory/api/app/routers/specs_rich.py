"""REST additive para campos ricos do Kanban Spec (kanban-planka task_05).

Prefixo ``/api/v1/specs`` — não altera contratos legados. Spec permanece SoT;
mutações disparam ``mirror_task`` quando ``PLANKA_MIRROR_SYNC`` está ativo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    TaskAttachment,
    TaskCard,
    TaskCardLabel,
    TaskChecklist,
    TaskChecklistItem,
    TaskLabel,
    TaskMember,
)
from app.routers.specs import (
    TaskResponse,
    _assert_access,
    _enrich_task,
    _get_task_or_404,
    _get_workspace_or_404,
)
from app.utils.planka_hooks import mirror_task
from app.utils.spec_attachments import (
    build_storage_key,
    delete_file,
    read_bytes,
    write_bytes,
)
from app.utils.spec_auth import resolve_spec_actor

router = APIRouter(prefix="/api/v1/specs", tags=["specs-rich"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class LabelCreate(BaseModel):
    name: str
    color: Optional[str] = None


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    color: Optional[str] = None
    created_at: Optional[datetime] = None


class ChecklistCreate(BaseModel):
    title: str = "Checklist"
    position: Optional[float] = None


class ChecklistItemCreate(BaseModel):
    title: str
    position: Optional[float] = None


class ChecklistItemPatch(BaseModel):
    title: Optional[str] = None
    is_completed: Optional[bool] = None
    position: Optional[float] = None


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    checklist_id: UUID
    title: str
    is_completed: bool
    position: float
    created_at: Optional[datetime] = None


class ChecklistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    title: str
    position: float
    created_at: Optional[datetime] = None
    items: list[ChecklistItemResponse] = []


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_by: Optional[str] = None
    created_at: Optional[datetime] = None


class MemberCreate(BaseModel):
    member: str


# --------------------------------------------------------------------------- #
# Labels
# --------------------------------------------------------------------------- #
@router.get("/workspaces/{workspace_id}/labels", response_model=list[LabelResponse])
def list_labels(workspace_id: UUID, db: Session = Depends(get_db)) -> list[LabelResponse]:
    _get_workspace_or_404(db, workspace_id)
    _assert_access(db, workspace_id)
    rows = (
        db.query(TaskLabel)
        .filter(TaskLabel.workspace_id == workspace_id)
        .order_by(TaskLabel.name.asc())
        .all()
    )
    return [LabelResponse.model_validate(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/labels",
    response_model=LabelResponse,
    status_code=201,
)
def create_label(
    workspace_id: UUID,
    payload: LabelCreate,
    db: Session = Depends(get_db),
) -> LabelResponse:
    _get_workspace_or_404(db, workspace_id)
    _assert_access(db, workspace_id)
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name obrigatório")
    label = TaskLabel(workspace_id=workspace_id, name=name, color=payload.color)
    db.add(label)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="label já existe neste workspace") from exc
    db.refresh(label)
    return LabelResponse.model_validate(label)


@router.post("/tasks/{task_id}/labels/{label_id}", response_model=TaskResponse)
def attach_label(
    task_id: UUID,
    label_id: UUID,
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    label = db.query(TaskLabel).filter(TaskLabel.id == label_id).first()
    if label is None or label.workspace_id != task.workspace_id:
        raise HTTPException(status_code=404, detail="Label não encontrada")
    exists = (
        db.query(TaskCardLabel)
        .filter(TaskCardLabel.task_id == task_id, TaskCardLabel.label_id == label_id)
        .first()
    )
    if not exists:
        db.add(TaskCardLabel(task_id=task_id, label_id=label_id))
        db.commit()
        mirror_task(db, task_id)
    return _enrich_task(db, task)


@router.delete("/tasks/{task_id}/labels/{label_id}", status_code=204)
def detach_label(
    task_id: UUID,
    label_id: UUID,
    db: Session = Depends(get_db),
) -> Response:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    deleted = (
        db.query(TaskCardLabel)
        .filter(TaskCardLabel.task_id == task_id, TaskCardLabel.label_id == label_id)
        .delete()
    )
    if deleted:
        db.commit()
        mirror_task(db, task_id)
    return Response(status_code=204)


@router.get("/tasks/{task_id}/labels", response_model=list[LabelResponse])
def list_task_labels(task_id: UUID, db: Session = Depends(get_db)) -> list[LabelResponse]:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    rows = (
        db.query(TaskLabel)
        .join(TaskCardLabel, TaskCardLabel.label_id == TaskLabel.id)
        .filter(TaskCardLabel.task_id == task_id)
        .order_by(TaskLabel.name.asc())
        .all()
    )
    return [LabelResponse.model_validate(r) for r in rows]


@router.get(
    "/tasks/{task_id}/attachments",
    response_model=list[AttachmentResponse],
)
def list_attachments(
    task_id: UUID, db: Session = Depends(get_db)
) -> list[AttachmentResponse]:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    rows = (
        db.query(TaskAttachment)
        .filter(TaskAttachment.task_id == task_id)
        .order_by(TaskAttachment.created_at.asc())
        .all()
    )
    return [AttachmentResponse.model_validate(r) for r in rows]


# --------------------------------------------------------------------------- #
# Checklists
# --------------------------------------------------------------------------- #
def _checklist_response(db: Session, checklist: TaskChecklist) -> ChecklistResponse:
    items = (
        db.query(TaskChecklistItem)
        .filter(TaskChecklistItem.checklist_id == checklist.id)
        .order_by(TaskChecklistItem.position.asc())
        .all()
    )
    data = ChecklistResponse.model_validate(checklist)
    data.items = [ChecklistItemResponse.model_validate(i) for i in items]
    return data


@router.get("/tasks/{task_id}/checklists", response_model=list[ChecklistResponse])
def list_checklists(task_id: UUID, db: Session = Depends(get_db)) -> list[ChecklistResponse]:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    rows = (
        db.query(TaskChecklist)
        .filter(TaskChecklist.task_id == task_id)
        .order_by(TaskChecklist.position.asc())
        .all()
    )
    return [_checklist_response(db, c) for c in rows]


@router.post(
    "/tasks/{task_id}/checklists",
    response_model=ChecklistResponse,
    status_code=201,
)
def create_checklist(
    task_id: UUID,
    payload: ChecklistCreate,
    db: Session = Depends(get_db),
) -> ChecklistResponse:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    checklist = TaskChecklist(
        task_id=task_id,
        title=(payload.title or "Checklist").strip() or "Checklist",
        position=payload.position if payload.position is not None else 65536.0,
    )
    db.add(checklist)
    db.commit()
    db.refresh(checklist)
    mirror_task(db, task_id)
    return _checklist_response(db, checklist)


@router.post(
    "/checklists/{checklist_id}/items",
    response_model=ChecklistItemResponse,
    status_code=201,
)
def create_checklist_item(
    checklist_id: UUID,
    payload: ChecklistItemCreate,
    db: Session = Depends(get_db),
) -> ChecklistItemResponse:
    checklist = db.query(TaskChecklist).filter(TaskChecklist.id == checklist_id).first()
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist não encontrada")
    task = _get_task_or_404(db, checklist.task_id)
    _assert_access(db, task.workspace_id)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title obrigatório")
    item = TaskChecklistItem(
        checklist_id=checklist_id,
        title=title,
        position=payload.position if payload.position is not None else 65536.0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    mirror_task(db, task.id)
    return ChecklistItemResponse.model_validate(item)


@router.patch(
    "/checklists/{checklist_id}/items/{item_id}",
    response_model=ChecklistItemResponse,
)
def patch_checklist_item(
    checklist_id: UUID,
    item_id: UUID,
    payload: ChecklistItemPatch,
    db: Session = Depends(get_db),
) -> ChecklistItemResponse:
    checklist = db.query(TaskChecklist).filter(TaskChecklist.id == checklist_id).first()
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist não encontrada")
    task = _get_task_or_404(db, checklist.task_id)
    _assert_access(db, task.workspace_id)
    item = (
        db.query(TaskChecklistItem)
        .filter(
            TaskChecklistItem.id == item_id,
            TaskChecklistItem.checklist_id == checklist_id,
        )
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    if payload.title is not None:
        item.title = payload.title.strip() or item.title
    if payload.is_completed is not None:
        item.is_completed = payload.is_completed
    if payload.position is not None:
        item.position = payload.position
    db.commit()
    db.refresh(item)
    mirror_task(db, task.id)
    return ChecklistItemResponse.model_validate(item)


# --------------------------------------------------------------------------- #
# Attachments (volume dedicado — nunca Qdrant)
# --------------------------------------------------------------------------- #
@router.post(
    "/tasks/{task_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    task_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> AttachmentResponse:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    data = await file.read()
    filename = file.filename or "upload.bin"
    key = build_storage_key(task_id, filename)
    size = write_bytes(key, data)
    actor = resolve_spec_actor()
    att = TaskAttachment(
        task_id=task_id,
        filename=filename,
        content_type=file.content_type,
        size_bytes=size,
        storage_key=key,
        uploaded_by=actor,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    mirror_task(db, task_id)
    return AttachmentResponse.model_validate(att)


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: UUID, db: Session = Depends(get_db)) -> Response:
    att = db.query(TaskAttachment).filter(TaskAttachment.id == attachment_id).first()
    if att is None:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    task = _get_task_or_404(db, att.task_id)
    _assert_access(db, task.workspace_id)
    try:
        data = read_bytes(att.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Arquivo ausente no storage") from exc
    headers = {"Content-Disposition": f'attachment; filename="{att.filename}"'}
    return Response(
        content=data,
        media_type=att.content_type or "application/octet-stream",
        headers=headers,
    )


@router.delete("/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: UUID, db: Session = Depends(get_db)) -> Response:
    att = db.query(TaskAttachment).filter(TaskAttachment.id == attachment_id).first()
    if att is None:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    task = _get_task_or_404(db, att.task_id)
    _assert_access(db, task.workspace_id)
    try:
        delete_file(att.storage_key)
    except OSError:
        pass
    task_id = att.task_id
    db.delete(att)
    db.commit()
    mirror_task(db, task_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Members (additive helpers; PATCH /tasks/{id} também aceita members)
# --------------------------------------------------------------------------- #
@router.post("/tasks/{task_id}/members", response_model=TaskResponse, status_code=201)
def add_member(
    task_id: UUID,
    payload: MemberCreate,
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    name = (payload.member or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="member obrigatório")
    exists = (
        db.query(TaskMember)
        .filter(TaskMember.task_id == task_id, TaskMember.member == name)
        .first()
    )
    if not exists:
        db.add(TaskMember(task_id=task_id, member=name))
        db.commit()
        mirror_task(db, task_id)
    db.refresh(task)
    return _enrich_task(db, task)


@router.delete("/tasks/{task_id}/members/{member}", response_model=TaskResponse)
def remove_member(
    task_id: UUID,
    member: str,
    db: Session = Depends(get_db),
) -> TaskResponse:
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id)
    db.query(TaskMember).filter(
        TaskMember.task_id == task_id, TaskMember.member == member
    ).delete()
    db.commit()
    mirror_task(db, task_id)
    db.refresh(task)
    return _enrich_task(db, task)
