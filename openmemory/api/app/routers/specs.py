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
    DocumentOrigin,
    DocumentType,
    SpecDocument,
    SpecDocumentVersion,
    SpecWorkspace,
    SpecWorkspaceStatus,
    TaskCard,
    TaskCardStatus,
)
from app.utils.permissions import get_accessible_spec_workspace_ids
from app.utils.projects import upsert_project
from app.utils.spec_versioning import write_document_version
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
    # Garante o Project no catálogo (FK) sem administração manual (ADR-002).
    upsert_project(payload.project_id, session=db)

    existing = (
        db.query(SpecWorkspace)
        .filter(
            SpecWorkspace.project_id == payload.project_id,
            SpecWorkspace.slug == payload.slug,
        )
        .first()
    )
    if existing is not None:
        response.status_code = 200
        return existing

    ws = SpecWorkspace(
        project_id=payload.project_id,
        slug=payload.slug,
        name=payload.name,
        status=payload.status or SpecWorkspaceStatus.planejamento,
        created_by=payload.created_by,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    response.status_code = 201
    return ws


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
    accessible = get_accessible_spec_workspace_ids(db, subject_type, subject_id)
    if accessible is not None:
        workspaces = [w for w in workspaces if w.id in accessible]

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
