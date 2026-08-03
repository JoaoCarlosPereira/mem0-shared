"""Store endpoints backed by AgentRegistry metadata."""

from __future__ import annotations

import os
from typing import Literal, Optional

from app.services.store_recipes import (
    InstallRecipeService,
    StoreRecipeError,
)
from app.utils.logging_context import auth_method_var, auth_user_var, team_var
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/store", tags=["store"])


class InstallRecipeRequest(BaseModel):
    kind: Literal["skill", "mcpserver", "prompt", "agent", "plugin"]
    name: str = Field(min_length=1, max_length=128)
    tag: str = Field(min_length=1, max_length=128)
    target: Literal["cursor", "claude", "codex"]


def get_install_recipe_service() -> InstallRecipeService:
    return InstallRecipeService()


def _current_actor_id() -> str:
    method = auth_method_var.get()
    if auth_user_var.get():
        return auth_user_var.get()
    if team_var.get():
        return f"team:{team_var.get()}"
    if method == "legacy":
        return "legacy"
    if not method and (os.getenv("AUTH_MODE", "warn").strip().lower() == "off"):
        return "auth-off"
    raise HTTPException(status_code=401, detail="credencial ausente")


def _registry_auth_headers(request: Request) -> Optional[dict[str, str]]:
    headers: dict[str, str] = {}
    authorization = request.headers.get("authorization")
    if authorization:
        headers["Authorization"] = authorization
    api_key = request.headers.get("x-api-key")
    if api_key:
        headers["X-API-Key"] = api_key
    return headers or None


@router.post("/install-recipes")
async def build_install_recipe(
    payload: InstallRecipeRequest,
    request: Request,
    service: InstallRecipeService = Depends(get_install_recipe_service),
) -> dict:
    """Return a host-applied install recipe for a catalog resource."""
    try:
        return await service.build(
            kind=payload.kind,
            name=payload.name,
            tag=payload.tag,
            target=payload.target,
            user_id=_current_actor_id(),
            auth_headers=_registry_auth_headers(request),
        )
    except StoreRecipeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
