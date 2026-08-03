"""HTTP client for the internal PLANKA sidecar (Spec mirror).

OpenMemory Spec tables remain the source of truth (ADR-005). This module is
the integration seam that projects Spec workspaces/tasks/documents onto PLANKA
Project/Board/List/Card IDs via ``spec_planka_id_map``. It never talks to
Qdrant and only calls the PLANKA REST API.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Protocol
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.models import (
    SpecDocument,
    SpecPlankaIdMap,
    SpecWorkspace,
    TaskCard,
    TaskCardStatus,
    parse_document_type,
)

DEFAULT_PLANKA_BASE_URL = "http://planka:1337"
DEFAULT_PLANKA_TIMEOUT_SECONDS = 5.0

# Spec Kanban column → PLANKA list display name (pipeline SDD).
SPEC_STATUS_TO_LIST_NAME: dict[str, str] = {
    TaskCardStatus.tasks.value: "Tasks",
    TaskCardStatus.em_andamento.value: "Em andamento",
    TaskCardStatus.revisao_codigo.value: "Revisão de código",
    TaskCardStatus.fase_teste.value: "Fase de teste",
    TaskCardStatus.concluido.value: "Concluído",
}

DOCUMENT_LIST_NAME = "Documentos"
DOCUMENT_LIST_ENTITY = "list:documentos"

ENTITY_PROJECT = "project"
ENTITY_BOARD = "board"
ENTITY_TASK = "task"
ENTITY_DOCUMENT = "document"

# Gap-based list positions (PLANKA convention).
_LIST_POSITION_STEP = 65536


class PlankaMirrorError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class PlankaMirrorNotFound(PlankaMirrorError):
    def __init__(self, detail: str = "recurso Spec não encontrado para espelho PLANKA"):
        super().__init__(404, detail)


class PlankaMirrorClient(Protocol):
    async def ensure_workspace_board(self, workspace_id: UUID) -> str: ...

    async def mirror_task(self, task_id: UUID) -> None: ...

    async def mirror_task_status(self, task_id: UUID) -> None: ...

    async def mirror_document(self, workspace_id: UUID, doc_type: str) -> None: ...

    async def delete_task(self, task_id: UUID) -> None: ...


def list_entity_type(status: str) -> str:
    """Entity type key for a Spec status list mapping."""
    return f"list:{status}"


def status_to_list_name(status: str) -> str:
    """Map Spec ``TaskCardStatus`` value to PLANKA list name."""
    key = (status or "").strip()
    if key not in SPEC_STATUS_TO_LIST_NAME:
        raise PlankaMirrorError(400, f"status Spec inválido para lista PLANKA: {status!r}")
    return SPEC_STATUS_TO_LIST_NAME[key]


class PlankaMirrorHttpClient:
    """Async PLANKA mirror client (pattern aligned with AgentRegistryHttpClient)."""

    def __init__(
        self,
        db: Session,
        *,
        base_url: Optional[str] = None,
        timeout_seconds: float = DEFAULT_PLANKA_TIMEOUT_SECONDS,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        raw_base_url = (
            base_url
            or os.getenv("PLANKA_BASE_URL")
            or os.getenv("PLANKA_INTERNAL_URL")
            or DEFAULT_PLANKA_BASE_URL
        )
        self.db = db
        self.base_url = raw_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    async def ensure_workspace_board(self, workspace_id: UUID) -> str:
        workspace = self.db.query(SpecWorkspace).filter(SpecWorkspace.id == workspace_id).first()
        if not workspace:
            raise PlankaMirrorNotFound(f"SpecWorkspace {workspace_id} não encontrado")

        existing_board = self._get_map(ENTITY_BOARD, workspace_id)
        if existing_board:
            await self._ensure_pipeline_lists(workspace_id, existing_board.planka_id)
            self.db.commit()
            return existing_board.planka_id

        project_map = self._get_map(ENTITY_PROJECT, workspace_id)
        if project_map:
            project_id = project_map.planka_id
        else:
            project_payload = await self._request(
                "POST",
                "/api/projects",
                json={
                    "type": "shared",
                    "name": _truncate(workspace.name or workspace.slug, 128),
                    "description": f"Spec workspace {workspace.slug} ({workspace.project_id})",
                },
            )
            project_id = _item_id(project_payload)
            self._upsert_map(ENTITY_PROJECT, workspace_id, project_id)

        board_payload = await self._request(
            "POST",
            f"/api/projects/{project_id}/boards",
            json={
                "position": _LIST_POSITION_STEP,
                "name": _truncate(workspace.name or workspace.slug, 128),
            },
        )
        board_id = _item_id(board_payload)
        self._upsert_map(ENTITY_BOARD, workspace_id, board_id)
        await self._ensure_pipeline_lists(workspace_id, board_id)
        self.db.commit()
        return board_id

    async def mirror_task(self, task_id: UUID) -> None:
        task = self.db.query(TaskCard).filter(TaskCard.id == task_id).first()
        if not task:
            raise PlankaMirrorNotFound(f"TaskCard {task_id} não encontrada")

        board_id = await self.ensure_workspace_board(task.workspace_id)
        list_id = await self._list_id_for_status(task.workspace_id, board_id, task.status.value)
        existing = self._get_map(ENTITY_TASK, task_id)
        body = {
            "name": _truncate(task.title, 1024),
            "description": task.description,
            "type": "project",
        }
        if existing:
            await self._request(
                "PATCH",
                f"/api/cards/{existing.planka_id}",
                json={**body, "listId": list_id, "position": _LIST_POSITION_STEP},
            )
        else:
            created = await self._request(
                "POST",
                f"/api/lists/{list_id}/cards",
                json={**body, "position": _LIST_POSITION_STEP},
            )
            self._upsert_map(ENTITY_TASK, task_id, _item_id(created))
        self.db.commit()

    async def mirror_task_status(self, task_id: UUID) -> None:
        task = self.db.query(TaskCard).filter(TaskCard.id == task_id).first()
        if not task:
            raise PlankaMirrorNotFound(f"TaskCard {task_id} não encontrada")

        board_id = await self.ensure_workspace_board(task.workspace_id)
        list_id = await self._list_id_for_status(task.workspace_id, board_id, task.status.value)
        existing = self._get_map(ENTITY_TASK, task_id)
        if not existing:
            # Card still missing — full mirror creates it in the right list.
            await self.mirror_task(task_id)
            return

        await self._request(
            "PATCH",
            f"/api/cards/{existing.planka_id}",
            json={"listId": list_id, "position": _LIST_POSITION_STEP},
        )
        self.db.commit()

    async def mirror_document(self, workspace_id: UUID, doc_type: str) -> None:
        workspace = self.db.query(SpecWorkspace).filter(SpecWorkspace.id == workspace_id).first()
        if not workspace:
            raise PlankaMirrorNotFound(f"SpecWorkspace {workspace_id} não encontrado")

        resolved = parse_document_type(doc_type)
        document = (
            self.db.query(SpecDocument)
            .filter(
                SpecDocument.workspace_id == workspace_id,
                SpecDocument.document_type == resolved,
            )
            .first()
        )
        if not document:
            raise PlankaMirrorNotFound(
                f"SpecDocument {resolved.value} não encontrado no workspace {workspace_id}"
            )

        board_id = await self.ensure_workspace_board(workspace_id)
        docs_list_id = await self._ensure_document_list(workspace_id, board_id)
        title = f"[{resolved.value}] {workspace.name}"
        body = {
            "name": _truncate(title, 1024),
            "description": document.current_content,
            "type": "project",
        }
        existing = self._get_map(ENTITY_DOCUMENT, document.id)
        if existing:
            await self._request(
                "PATCH",
                f"/api/cards/{existing.planka_id}",
                json={**body, "listId": docs_list_id, "position": _LIST_POSITION_STEP},
            )
        else:
            created = await self._request(
                "POST",
                f"/api/lists/{docs_list_id}/cards",
                json={**body, "position": _LIST_POSITION_STEP},
            )
            self._upsert_map(ENTITY_DOCUMENT, document.id, _item_id(created))
        self.db.commit()

    async def delete_task(self, task_id: UUID) -> None:
        existing = self._get_map(ENTITY_TASK, task_id)
        if not existing:
            return
        try:
            await self._request("DELETE", f"/api/cards/{existing.planka_id}")
        except PlankaMirrorError as exc:
            if exc.status_code != 404:
                raise
        self.db.delete(existing)
        self.db.commit()

    async def _ensure_pipeline_lists(self, workspace_id: UUID, board_id: str) -> None:
        for index, status in enumerate(SPEC_STATUS_TO_LIST_NAME):
            entity = list_entity_type(status)
            if self._get_map(entity, workspace_id):
                continue
            created = await self._request(
                "POST",
                f"/api/boards/{board_id}/lists",
                json={
                    "type": "active",
                    "position": _LIST_POSITION_STEP * (index + 1),
                    "name": SPEC_STATUS_TO_LIST_NAME[status],
                },
            )
            self._upsert_map(entity, workspace_id, _item_id(created))

    async def _ensure_document_list(self, workspace_id: UUID, board_id: str) -> str:
        existing = self._get_map(DOCUMENT_LIST_ENTITY, workspace_id)
        if existing:
            return existing.planka_id
        created = await self._request(
            "POST",
            f"/api/boards/{board_id}/lists",
            json={
                "type": "active",
                "position": _LIST_POSITION_STEP * (len(SPEC_STATUS_TO_LIST_NAME) + 1),
                "name": DOCUMENT_LIST_NAME,
            },
        )
        planka_id = _item_id(created)
        self._upsert_map(DOCUMENT_LIST_ENTITY, workspace_id, planka_id)
        return planka_id

    async def _list_id_for_status(
        self, workspace_id: UUID, board_id: str, status: str
    ) -> str:
        entity = list_entity_type(status)
        # Validate status early.
        status_to_list_name(status)
        mapped = self._get_map(entity, workspace_id)
        if mapped:
            return mapped.planka_id
        await self._ensure_pipeline_lists(workspace_id, board_id)
        mapped = self._get_map(entity, workspace_id)
        if not mapped:
            raise PlankaMirrorError(502, f"lista PLANKA ausente para status {status!r}")
        return mapped.planka_id

    def _get_map(self, entity_type: str, spec_id: UUID) -> Optional[SpecPlankaIdMap]:
        return (
            self.db.query(SpecPlankaIdMap)
            .filter(
                SpecPlankaIdMap.entity_type == entity_type,
                SpecPlankaIdMap.spec_id == spec_id,
            )
            .first()
        )

    def _upsert_map(self, entity_type: str, spec_id: UUID, planka_id: str) -> SpecPlankaIdMap:
        row = self._get_map(entity_type, spec_id)
        if row:
            row.planka_id = planka_id
        else:
            row = SpecPlankaIdMap(
                entity_type=entity_type,
                spec_id=spec_id,
                planka_id=planka_id,
            )
            self.db.add(row)
        self.db.flush()
        return row

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        request_headers = self._headers(headers=headers)
        client_kwargs: dict[str, Any] = {"timeout": self.timeout_seconds}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json,
                    headers=request_headers,
                )
            except httpx.TimeoutException as exc:
                raise PlankaMirrorError(504, "PLANKA timeout") from exc
            except httpx.RequestError as exc:
                raise PlankaMirrorError(502, "PLANKA indisponível") from exc
        return _json_response(response)

    def _headers(self, *, headers: Optional[dict[str, str]] = None) -> dict[str, str]:
        merged = {"Accept": "application/json", "Content-Type": "application/json"}
        if headers:
            merged.update(headers)
        if token := _env_auth_token():
            merged["Authorization"] = f"Bearer {token}"
        return merged


def _item_id(payload: dict[str, Any]) -> str:
    item = payload.get("item") if isinstance(payload, dict) else None
    if not isinstance(item, dict) or item.get("id") is None:
        raise PlankaMirrorError(502, "PLANKA retornou item sem id")
    return str(item["id"])


def _truncate(value: Optional[str], max_len: int) -> str:
    text = (value or "").strip() or "untitled"
    return text[:max_len]


def _json_response(response: httpx.Response) -> dict[str, Any]:
    if response.status_code == 404:
        raise PlankaMirrorError(404, "PLANKA recurso não encontrado")
    if response.status_code in (401, 403):
        raise PlankaMirrorError(response.status_code, "PLANKA negou acesso ao recurso")
    if response.status_code >= 500:
        raise PlankaMirrorError(502, f"PLANKA retornou HTTP {response.status_code}")
    if response.status_code >= 400:
        raise PlankaMirrorError(
            response.status_code, f"PLANKA retornou HTTP {response.status_code}"
        )
    if response.status_code == 204 or not response.content:
        return {}
    try:
        data = response.json()
    except ValueError as exc:
        raise PlankaMirrorError(502, "PLANKA retornou JSON inválido") from exc
    if not isinstance(data, dict):
        raise PlankaMirrorError(502, "PLANKA retornou payload inválido")
    return data


def _env_auth_token() -> Optional[str]:
    for name in (
        "PLANKA_INTERNAL_ACCESS_TOKEN",
        "INTERNAL_ACCESS_TOKEN",
        "PLANKA_BEARER_TOKEN",
        "PLANKA_AUTH_TOKEN",
    ):
        token = (os.getenv(name) or "").strip()
        if token:
            return token
    return None


__all__ = [
    "DOCUMENT_LIST_ENTITY",
    "DOCUMENT_LIST_NAME",
    "DEFAULT_PLANKA_BASE_URL",
    "DEFAULT_PLANKA_TIMEOUT_SECONDS",
    "ENTITY_BOARD",
    "ENTITY_DOCUMENT",
    "ENTITY_PROJECT",
    "ENTITY_TASK",
    "PlankaMirrorClient",
    "PlankaMirrorError",
    "PlankaMirrorHttpClient",
    "PlankaMirrorNotFound",
    "SPEC_STATUS_TO_LIST_NAME",
    "list_entity_type",
    "status_to_list_name",
]
