"""Router REST do espaço compartilhado de specs — workspaces e documentos (Tarefa 3).

Expõe criação/consulta de ``SpecWorkspace`` e gravação/consulta versionada de
``SpecDocument`` (PRD/TechSpec/Tasks). Toda leitura/escrita passa pela checagem
de ``AccessControl`` (``object_type="spec_workspace"``) reaproveitada de
``get_accessible_spec_workspace_ids``. A gravação delega o controle de conflito
para ``write_document_version`` (Tarefa 2), retornando 409 quando a versão
esperada está desatualizada (ADR-005). A mesma lógica é reaproveitada pelas
tools MCP (Tarefa 7), sem duplicação.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.models import (
    CommentTargetType,
    DocumentOrigin,
    DocumentType,
    SpecComment,
    SpecDocument,
    SpecDocumentVersion,
    SpecWorkspace,
    SpecWorkspaceStatus,
    TaskCard,
    TaskCardStatus,
    TaskStatusHistory,
)
from app.utils.permissions import get_accessible_spec_workspace_ids
from app.utils.projects import upsert_project
from app.utils.spec_search import search_specs
from app.utils.spec_versioning import write_document_version
from app.utils.task_lock import claim_task, release_task, update_task_status
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/specs", tags=["specs"])


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class WorkspaceCreate(BaseModel):
    project_id: str
    slug: str
    name: str
    status: Optional[SpecWorkspaceStatus] = None
    created_by: Optional[str] = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: str
    slug: str
    name: str
    status: SpecWorkspaceStatus
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkspaceSummaryResponse(BaseModel):
    """Item do painel de Projeto: workspace + progresso resumido por status."""
    id: UUID
    project_id: str
    slug: str
    name: str
    status: SpecWorkspaceStatus
    task_counts: dict[str, int]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    document_type: DocumentType
    current_version: int
    current_content: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    title: str
    description: Optional[str] = None
    status: TaskCardStatus
    is_blocked: bool
    block_reason: Optional[str] = None
    assignee: Optional[str] = None
    version: int
    last_activity_at: Optional[datetime] = None
    branch_ref: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkspaceBoardResponse(BaseModel):
    workspace: WorkspaceResponse
    documents: list[DocumentResponse]
    tasks: list[TaskResponse]


class DocumentWriteRequest(BaseModel):
    content: str
    expected_version: Optional[int] = None
    author: Optional[str] = None


class DocumentWriteResponse(BaseModel):
    document_id: UUID
    version: int
    conflict: bool = False


class VersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    content: str
    author: Optional[str] = None
    origin: DocumentOrigin
    created_at: Optional[datetime] = None


class TaskCreate(BaseModel):
    workspace_id: UUID
    title: str
    description: Optional[str] = None
    branch_ref: Optional[str] = None


class TaskUpdate(BaseModel):
    """Atualização parcial de metadados da task (título/descrição/branch)."""
    title: Optional[str] = None
    description: Optional[str] = None
    branch_ref: Optional[str] = None
    expected_version: int


class ClaimRequest(BaseModel):
    claimant: str


class ReleaseRequest(BaseModel):
    actor: Optional[str] = None
    reason: Optional[str] = None


class StatusPatchRequest(BaseModel):
    expected_version: int
    new_status: Optional[TaskCardStatus] = None
    actor: Optional[str] = None
    is_blocked: Optional[bool] = None
    block_reason: Optional[str] = None


class CommentCreate(BaseModel):
    target_type: CommentTargetType
    target_id: UUID
    body: str
    author: Optional[str] = None


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target_type: CommentTargetType
    target_id: UUID
    author: Optional[str] = None
    body: str
    created_at: Optional[datetime] = None


class SpecSearchResult(BaseModel):
    id: Optional[str] = None
    score: Optional[float] = None
    content: Optional[str] = None
    project: Optional[str] = None
    workspace_id: Optional[str] = None
    document_type: Optional[str] = None
    group_id: Optional[str] = None
    owner: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_workspace_or_404(db: Session, workspace_id: UUID) -> SpecWorkspace:
    ws = db.query(SpecWorkspace).filter(SpecWorkspace.id == workspace_id).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace não encontrado")
    return ws


def _assert_access(
    db: Session,
    workspace_id: UUID,
    subject_type: str,
    subject_id: Optional[UUID],
) -> None:
    """Nega (403) se o sujeito tem regras de acesso mas nenhuma inclui este workspace."""
    accessible = get_accessible_spec_workspace_ids(db, subject_type, subject_id)
    if accessible is not None and workspace_id not in accessible:
        raise HTTPException(status_code=403, detail="Sem permissão para este workspace")


def _get_document_or_404(
    db: Session, workspace_id: UUID, document_type: DocumentType
) -> SpecDocument:
    doc = (
        db.query(SpecDocument)
        .filter(
            SpecDocument.workspace_id == workspace_id,
            SpecDocument.document_type == document_type,
        )
        .first()
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return doc


def get_or_create_workspace(
    db: Session,
    *,
    project_id: str,
    slug: str,
    name: str,
    created_by: Optional[str] = None,
    status: Optional[SpecWorkspaceStatus] = None,
) -> tuple[SpecWorkspace, bool]:
    """Cria ou retorna o workspace de ``(project_id, slug)`` — idempotente.

    Lógica compartilhada entre o endpoint REST e a tool MCP (sem duplicação).
    Retorna ``(workspace, created)``; garante o Project no catálogo via
    ``upsert_project``.
    """
    upsert_project(project_id, session=db)
    existing = (
        db.query(SpecWorkspace)
        .filter(SpecWorkspace.project_id == project_id, SpecWorkspace.slug == slug)
        .first()
    )
    if existing is not None:
        return existing, False

    ws = SpecWorkspace(
        project_id=project_id,
        slug=slug,
        name=name,
        status=status or SpecWorkspaceStatus.planejamento,
        created_by=created_by,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws, True


def get_or_create_document(
    db: Session, workspace_id: UUID, document_type: DocumentType
) -> SpecDocument:
    """Retorna o ``SpecDocument`` do tipo dado no workspace, criando-o se ausente."""
    doc = (
        db.query(SpecDocument)
        .filter(
            SpecDocument.workspace_id == workspace_id,
            SpecDocument.document_type == document_type,
        )
        .first()
    )
    if doc is None:
        doc = SpecDocument(workspace_id=workspace_id, document_type=document_type)
        db.add(doc)
        db.commit()
        db.refresh(doc)
    return doc


def _get_task_or_404(db: Session, task_id: UUID) -> TaskCard:
    task = db.query(TaskCard).filter(TaskCard.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task não encontrada")
    return task


def _resolve_comment_target_workspace(
    db: Session, target_type: CommentTargetType, target_id: UUID
) -> UUID:
    """Valida que o alvo existe e devolve o ``workspace_id`` para a checagem de acesso."""
    if target_type == CommentTargetType.workspace:
        ws = db.query(SpecWorkspace).filter(SpecWorkspace.id == target_id).first()
        if ws is None:
            raise HTTPException(status_code=404, detail="Alvo do comentário não encontrado")
        return ws.id
    if target_type == CommentTargetType.document:
        doc = db.query(SpecDocument).filter(SpecDocument.id == target_id).first()
        if doc is None:
            raise HTTPException(status_code=404, detail="Alvo do comentário não encontrado")
        return doc.workspace_id
    task = db.query(TaskCard).filter(TaskCard.id == target_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Alvo do comentário não encontrado")
    return task.workspace_id


# --------------------------------------------------------------------------- #
# Workspaces
# --------------------------------------------------------------------------- #
@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(
    payload: WorkspaceCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    """Cria um workspace. Idempotente por ``(project_id, slug)``."""
    ws, created = get_or_create_workspace(
        db,
        project_id=payload.project_id,
        slug=payload.slug,
        name=payload.name,
        created_by=payload.created_by,
        status=payload.status,
    )
    response.status_code = 201 if created else 200
    return ws


def _build_summaries(
    db: Session, workspaces: list[SpecWorkspace]
) -> list[WorkspaceSummaryResponse]:
    """Monta os resumos (workspace + contagem de tasks por status).

    Contagem computada em uma única query agregada (``GROUP BY workspace_id,
    status``) — sem N+1, independentemente de quantos workspaces.
    """
    ws_ids = [w.id for w in workspaces]
    counts: dict[UUID, dict[str, int]] = {}
    if ws_ids:
        rows = (
            db.query(TaskCard.workspace_id, TaskCard.status, func.count().label("c"))
            .filter(TaskCard.workspace_id.in_(ws_ids))
            .group_by(TaskCard.workspace_id, TaskCard.status)
            .all()
        )
        for ws_id, status, count in rows:
            counts.setdefault(ws_id, {})[status.value] = count

    return [
        WorkspaceSummaryResponse(
            id=w.id,
            project_id=w.project_id,
            slug=w.slug,
            name=w.name,
            status=w.status,
            task_counts=counts.get(w.id, {}),
        )
        for w in workspaces
    ]


def _filter_accessible(
    db: Session,
    workspaces: list[SpecWorkspace],
    subject_type: str,
    subject_id: Optional[UUID],
) -> list[SpecWorkspace]:
    accessible = get_accessible_spec_workspace_ids(db, subject_type, subject_id)
    if accessible is None:
        return workspaces
    return [w for w in workspaces if w.id in accessible]


@router.get("/workspaces", response_model=list[WorkspaceSummaryResponse])
def list_all_workspaces(
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> list[WorkspaceSummaryResponse]:
    """Índice global: todos os workspaces acessíveis (de todos os projetos).

    Alimenta a tela inicial de Specs (lista os quadros agrupados por projeto).
    """
    workspaces = db.query(SpecWorkspace).order_by(SpecWorkspace.project_id).all()
    workspaces = _filter_accessible(db, workspaces, subject_type, subject_id)
    return _build_summaries(db, workspaces)


@router.get(
    "/projects/{project_id}/workspaces",
    response_model=list[WorkspaceSummaryResponse],
)
def list_project_workspaces(
    project_id: str,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> list[WorkspaceSummaryResponse]:
    """Painel de Projeto: workspaces + contagem de tasks por status.

    Progresso resumido computado em uma única query agregada
    (``GROUP BY workspace_id, status``) — sem N+1.
    """
    workspaces = (
        db.query(SpecWorkspace)
        .filter(SpecWorkspace.project_id == project_id)
        .all()
    )
    workspaces = _filter_accessible(db, workspaces, subject_type, subject_id)
    return _build_summaries(db, workspaces)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceBoardResponse)
def get_workspace_board(
    workspace_id: UUID,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> WorkspaceBoardResponse:
    """Quadro completo do workspace: documentos + tasks."""
    ws = _get_workspace_or_404(db, workspace_id)
    _assert_access(db, workspace_id, subject_type, subject_id)

    documents = (
        db.query(SpecDocument)
        .filter(SpecDocument.workspace_id == workspace_id)
        .all()
    )
    tasks = (
        db.query(TaskCard)
        .filter(TaskCard.workspace_id == workspace_id)
        .all()
    )
    return WorkspaceBoardResponse(workspace=ws, documents=documents, tasks=tasks)


# --------------------------------------------------------------------------- #
# Documentos
# --------------------------------------------------------------------------- #
@router.put(
    "/workspaces/{workspace_id}/documents/{document_type}",
    response_model=DocumentWriteResponse,
)
def write_workspace_document(
    workspace_id: UUID,
    document_type: DocumentType,
    payload: DocumentWriteRequest,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> DocumentWriteResponse:
    """Grava uma nova versão do documento. 409 em conflito de versão (ADR-005)."""
    _get_workspace_or_404(db, workspace_id)
    _assert_access(db, workspace_id, subject_type, subject_id)

    doc = get_or_create_document(db, workspace_id, document_type)

    author = payload.author or (str(subject_id) if subject_id else None)
    result = write_document_version(
        db,
        doc.id,
        payload.content,
        payload.expected_version,
        author,
        DocumentOrigin.api,
    )

    if result.conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "conflict": True,
                "current_version": result.version,
                "current_content": result.current_content,
            },
        )

    return DocumentWriteResponse(
        document_id=result.document_id,
        version=result.version,
        conflict=False,
    )


@router.get(
    "/workspaces/{workspace_id}/documents/{document_type}/versions",
    response_model=list[VersionResponse],
)
def list_document_versions(
    workspace_id: UUID,
    document_type: DocumentType,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> list[VersionResponse]:
    """Histórico de versões (snapshots) de um documento, em ordem crescente."""
    _get_workspace_or_404(db, workspace_id)
    _assert_access(db, workspace_id, subject_type, subject_id)
    doc = _get_document_or_404(db, workspace_id, document_type)

    return (
        db.query(SpecDocumentVersion)
        .filter(SpecDocumentVersion.document_id == doc.id)
        .order_by(SpecDocumentVersion.version.asc())
        .all()
    )


@router.delete(
    "/workspaces/{workspace_id}/documents/{document_type}",
    status_code=204,
)
def delete_workspace_document(
    workspace_id: UUID,
    document_type: DocumentType,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """Remove o documento do tipo dado e todo o histórico de versões."""
    _get_workspace_or_404(db, workspace_id)
    _assert_access(db, workspace_id, subject_type, subject_id)
    doc = _get_document_or_404(db, workspace_id, document_type)

    db.query(SpecComment).filter(
        SpecComment.target_type == CommentTargetType.document,
        SpecComment.target_id == doc.id,
    ).delete()
    db.query(SpecDocumentVersion).filter(
        SpecDocumentVersion.document_id == doc.id
    ).delete()
    db.delete(doc)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------------------- #
# Tasks
# --------------------------------------------------------------------------- #
@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    payload: TaskCreate,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Cria uma task; nasce na coluna ``tasks`` (backlog)."""
    _get_workspace_or_404(db, payload.workspace_id)
    _assert_access(db, payload.workspace_id, subject_type, subject_id)

    task = TaskCard(
        workspace_id=payload.workspace_id,
        title=payload.title,
        description=payload.description,
        branch_ref=payload.branch_ref,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Atualiza título/descrição/branch com concorrência otimista (ADR-005)."""
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id, subject_type, subject_id)

    if task.version != payload.expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "conflict": True,
                "current_version": task.version,
                "title": task.title,
                "description": task.description,
            },
        )

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.branch_ref is not None:
        task.branch_ref = payload.branch_ref
    task.version = task.version + 1
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a task e o histórico de status associado."""
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id, subject_type, subject_id)

    db.query(TaskStatusHistory).filter(TaskStatusHistory.task_id == task_id).delete()
    db.query(SpecComment).filter(
        SpecComment.target_type == CommentTargetType.task,
        SpecComment.target_id == task_id,
    ).delete()
    db.delete(task)
    db.commit()
    return Response(status_code=204)


@router.post("/tasks/{task_id}/claim", response_model=TaskResponse)
def claim_task_endpoint(
    task_id: UUID,
    payload: ClaimRequest,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Assume a task. 409 se já ativa com outro responsável (ADR-003)."""
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id, subject_type, subject_id)

    result = claim_task(db, task_id, payload.claimant)
    if not result.claimed:
        raise HTTPException(
            status_code=409,
            detail={
                "claimed": False,
                "current_assignee": result.current_assignee,
                "version": result.version,
            },
        )
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/release", response_model=TaskResponse)
def release_task_endpoint(
    task_id: UUID,
    payload: ReleaseRequest,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Libera a task manualmente: volta a ``tasks`` e limpa assignee/bloqueio."""
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id, subject_type, subject_id)

    release_task(db, task_id, payload.actor, payload.reason)
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
def patch_task_status(
    task_id: UUID,
    payload: StatusPatchRequest,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Muda a coluna e/ou o marcador de bloqueio com concorrência otimista.

    ``new_status`` omitido mantém a coluna atual (usado para reportar bloqueio =
    ``is_blocked=true`` sem mudar de coluna — ADR-007). 409 em conflito de versão.
    """
    task = _get_task_or_404(db, task_id)
    _assert_access(db, task.workspace_id, subject_type, subject_id)

    target_status = payload.new_status or task.status
    result = update_task_status(
        db,
        task_id,
        target_status,
        payload.expected_version,
        payload.actor,
        is_blocked=payload.is_blocked,
        block_reason=payload.block_reason,
    )
    if result.conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "conflict": True,
                "current_version": result.version,
                "current_status": result.status,
            },
        )
    db.refresh(task)
    return task


# --------------------------------------------------------------------------- #
# Comentários
# --------------------------------------------------------------------------- #
@router.post("/comments", response_model=CommentResponse, status_code=201)
def create_comment(
    payload: CommentCreate,
    subject_type: str = Query("user"),
    subject_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> CommentResponse:
    """Adiciona comentário a workspace/documento/task (valida o alvo antes)."""
    workspace_id = _resolve_comment_target_workspace(db, payload.target_type, payload.target_id)
    _assert_access(db, workspace_id, subject_type, subject_id)

    comment = SpecComment(
        target_type=payload.target_type,
        target_id=payload.target_id,
        author=payload.author,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


# --------------------------------------------------------------------------- #
# Busca semântica
# --------------------------------------------------------------------------- #
@router.get("/search", response_model=list[SpecSearchResult])
def search_specs_endpoint(
    q: str = Query(..., description="Consulta semântica"),
    project_id: Optional[str] = Query(None, description="Filtro opcional por projeto"),
    group: Optional[str] = Query(None, description="Grupo do solicitante (boost)"),
) -> list[SpecSearchResult]:
    """Busca semântica em specs concluídas, ordenada por relevância (ADR-006)."""
    return search_specs(q, project_id=project_id, requester_group=group)
