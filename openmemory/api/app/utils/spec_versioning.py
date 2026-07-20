"""Gravação versionada de documentos de spec com concorrência otimista (ADR-005).

Lógica de domínio pura (recebe ``db: Session``, sem dependência de FastAPI
``Request``/``Response``) reaproveitada pelo router REST (Tarefa 3) e pelas
tools MCP (Tarefa 7). Cada gravação bem-sucedida usa um
``UPDATE ... WHERE id = :id AND current_version = :expected`` atômico: se
nenhuma linha for afetada, a versão mudou entre a leitura e a gravação e o
resultado é um conflito, sem side-effects parciais (nenhuma
``SpecDocumentVersion`` nova é criada).
"""

import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import (
    DocumentOrigin,
    SpecAuditLog,
    SpecDocument,
    SpecDocumentVersion,
    get_current_utc_time,
)


@dataclass
class WriteDocumentResult:
    """Resultado de ``write_document_version`` (ver TechSpec — Interfaces).

    Em conflito, ``version``/``current_content`` refletem a versão vigente no
    banco para que o cliente possa reconciliar e tentar de novo.
    """
    document_id: uuid.UUID
    version: int
    conflict: bool
    current_content: str | None = None


def _coerce_origin(origin: DocumentOrigin | str) -> DocumentOrigin:
    return origin if isinstance(origin, DocumentOrigin) else DocumentOrigin(origin)


def write_document_version(
    db: Session,
    document_id: uuid.UUID,
    content: str,
    expected_version: int | None,
    author: str | None,
    origin: DocumentOrigin | str,
) -> WriteDocumentResult:
    """Grava uma nova versão (snapshot) de ``SpecDocument`` de forma atômica.

    ``expected_version=None`` só é válido na criação inicial (documento ainda
    sem versão, ``current_version == 0``). Um ``expected_version`` desatualizado
    retorna ``conflict=True`` sem alterar nada.
    """
    origin = _coerce_origin(origin)

    doc = db.get(SpecDocument, document_id)
    if doc is None:
        raise ValueError(f"SpecDocument {document_id} não encontrado")

    base = 0 if expected_version is None else expected_version
    new_version = base + 1
    now = get_current_utc_time()

    result = db.execute(
        sa.update(SpecDocument)
        .where(
            SpecDocument.id == document_id,
            SpecDocument.current_version == base,
        )
        .values(
            current_version=new_version,
            current_content=content,
            updated_by=author,
            updated_at=now,
        )
    )

    if result.rowcount == 0:
        # Conflito: versão mudou entre leitura e gravação. Descarta e relê.
        db.rollback()
        fresh = db.get(SpecDocument, document_id)
        return WriteDocumentResult(
            document_id=document_id,
            version=fresh.current_version,
            conflict=True,
            current_content=fresh.current_content,
        )

    db.add(
        SpecDocumentVersion(
            document_id=document_id,
            version=new_version,
            content=content,
            author=author,
            origin=origin,
        )
    )
    db.add(
        SpecAuditLog(
            workspace_id=doc.workspace_id,
            actor=author,
            action="write_spec_document",
            detail={
                "document_type": doc.document_type.value,
                "version": new_version,
            },
            origin=origin,
        )
    )
    db.commit()

    return WriteDocumentResult(
        document_id=document_id,
        version=new_version,
        conflict=False,
        current_content=None,
    )
