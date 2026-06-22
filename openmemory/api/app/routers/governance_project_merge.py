"""Governance endpoints for LLM-assisted duplicate project merge."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.governance.project_merge import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    preview_project_merges,
    run_merge_projects_job,
)
from app.utils.governance_queue import governance_queue

router = APIRouter(prefix="/admin/governance", tags=["governance"])


class MergeGroupSpec(BaseModel):
    canonical: str
    aliases: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    reason: str = "manual"


class MergeProjectsRequest(BaseModel):
    dry_run: bool = False
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    groups: Optional[List[MergeGroupSpec]] = None


@router.get("/projects/merge-preview")
def merge_projects_preview(
    confidence_threshold: float = Query(DEFAULT_CONFIDENCE_THRESHOLD, ge=0.0, le=1.0),
) -> dict:
    """Return LLM-suggested duplicate project groups without applying merges."""
    try:
        groups = preview_project_merges(confidence_threshold=confidence_threshold)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"groups": groups, "count": len(groups)}


@router.post("/projects/merge", status_code=202)
def enqueue_merge_projects(body: MergeProjectsRequest) -> Dict[str, Any]:
    """Enqueue a governance job to unify duplicate MCP projects."""
    payload: Dict[str, Any] = {
        "manual": True,
        "dry_run": body.dry_run,
        "confidence_threshold": body.confidence_threshold,
        "limit": 50,
    }
    if body.groups is not None:
        payload["groups"] = [g.model_dump() for g in body.groups]

    job_id = governance_queue.enqueue("merge_projects", payload=payload)
    return {
        "job_id": job_id,
        "job_type": "merge_projects",
        "status": "queued",
        "dry_run": body.dry_run,
    }


@router.post("/projects/merge-now")
def merge_projects_now(body: MergeProjectsRequest) -> Dict[str, Any]:
    """Run project merge synchronously (useful for dry-run / small catalogs)."""
    payload: Dict[str, Any] = {
        "dry_run": body.dry_run,
        "confidence_threshold": body.confidence_threshold,
    }
    if body.groups is not None:
        payload["groups"] = [g.model_dump() for g in body.groups]

    try:
        actions = run_merge_projects_job(
            project=None,
            job_id="manual-sync",
            limit=50,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    preview: List[Dict[str, Any]] = []
    if body.dry_run and body.groups is None:
        preview = preview_project_merges(confidence_threshold=body.confidence_threshold)

    return {
        "actions": actions,
        "dry_run": body.dry_run,
        "groups": preview,
    }
