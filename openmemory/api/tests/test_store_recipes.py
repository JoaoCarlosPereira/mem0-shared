import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.team_auth import AuthMiddleware
from app.services.store_recipes import (
    InstallRecipeService,
    InstallRecipeValidationError,
)

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "store.py"
_spec = importlib.util.spec_from_file_location("store_router_under_test", _PATH)
_store_router = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _store_router
_spec.loader.exec_module(_store_router)
store_router = _store_router.router
get_install_recipe_service = _store_router.get_install_recipe_service


class FakeRegistryClient:
    def __init__(self, resource):
        self.resource = resource
        self.calls = []

    async def get_resource(self, *, kind, name, tag, auth_headers=None):
        self.calls.append(
            {
                "kind": kind,
                "name": name,
                "tag": tag,
                "auth_headers": auth_headers,
            }
        )
        return self.resource


def skill_resource(**repository_overrides):
    repository = {
        "url": "https://example.invalid/team/skills.git",
        "commit": "abc123",
        "subfolder": "skills/team-skill",
    }
    repository.update(repository_overrides)
    return {
        "apiVersion": "ar.dev/v1alpha1",
        "kind": "Skill",
        "metadata": {"namespace": "default", "name": "team-skill", "tag": "v1"},
        "spec": {
            "title": "Team Skill",
            "description": "Reusable team skill",
            "source": {"repository": repository},
        },
    }


def mcp_resource():
    return {
        "apiVersion": "ar.dev/v1alpha1",
        "kind": "MCPServer",
        "metadata": {"namespace": "default", "name": "ctx7", "tag": "v1"},
        "spec": {
            "title": "Context7",
            "source": {
                "package": {
                    "registryType": "npm",
                    "identifier": "@upstash/context7-mcp",
                    "version": "1.2.3",
                }
            },
        },
    }


def packaged_skill_resource():
    resource = skill_resource()
    resource["status"] = {
        "resolvedSource": {
            "artifact": {
                "digest": "a" * 64,
                "mediaType": "application/vnd.agentregistry.skill.v1.tar+gzip",
                "size": 1234,
            }
        }
    }
    return resource


@pytest.mark.asyncio
async def test_cursor_skill_recipe_uses_cursor_skill_path_and_rollback():
    registry = FakeRegistryClient(skill_resource())
    service = InstallRecipeService(registry_client=registry)

    recipe = await service.build(
        kind="skill",
        name="team-skill",
        tag="v1",
        target="cursor",
        user_id="user-1",
    )

    assert recipe["target"] == "cursor"
    assert recipe["steps"][0]["type"] == "backup"
    assert recipe["steps"][1]["type"] == "copy"
    assert recipe["steps"][1]["to"] == ".cursor/skills/team-skill"
    assert recipe["source"]["subfolder"] == "skills/team-skill"
    assert recipe["rollback"] == [
        {
            "id": "restore-backup",
            "type": "restore_backup",
            "path": ".cursor/skills/team-skill",
            "if_backup_exists": True,
        }
    ]


@pytest.mark.asyncio
async def test_packaged_skill_recipe_prefers_complete_artifact_over_legacy_git():
    registry = FakeRegistryClient(packaged_skill_resource())
    recipe = await InstallRecipeService(registry_client=registry).build(
        kind="skill", name="team-skill", tag="v1", target="cursor", user_id="user-1"
    )

    assert recipe["source"]["type"] == "registry_artifact"
    assert recipe["steps"][1]["type"] == "download_and_extract"
    assert recipe["steps"][1]["verify_artifact_sha256"] == "a" * 64


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "expected_path"),
    [
        ("claude", "~/.claude/skills/team-skill"),
        ("codex", "~/.codex/skills/team-skill"),
    ],
)
async def test_claude_and_codex_skill_targets_are_covered(target, expected_path):
    registry = FakeRegistryClient(skill_resource())
    service = InstallRecipeService(registry_client=registry)

    recipe = await service.build(
        kind="skill",
        name="team-skill",
        tag="v1",
        target=target,
        user_id="user-1",
    )

    assert recipe["steps"][1]["to"] == expected_path
    assert recipe["steps"][2]["type"] == "verify"


@pytest.mark.asyncio
async def test_mcpserver_cursor_recipe_merges_cursor_json_config():
    registry = FakeRegistryClient(mcp_resource())
    service = InstallRecipeService(registry_client=registry)

    recipe = await service.build(
        kind="mcpserver",
        name="ctx7",
        tag="v1",
        target="cursor",
        user_id="user-1",
    )

    merge = recipe["steps"][1]
    assert merge["type"] == "merge_json"
    assert merge["path"] == ".cursor/mcp.json"
    assert merge["content"]["mcpServers"]["ctx7"]["command"] == "npx"
    assert (
        "@upstash/context7-mcp@1.2.3"
        in merge["content"]["mcpServers"]["ctx7"]["args"]
    )


@pytest.mark.asyncio
async def test_mcpserver_codex_recipe_merges_codex_toml_config():
    registry = FakeRegistryClient(mcp_resource())
    service = InstallRecipeService(registry_client=registry)

    recipe = await service.build(
        kind="mcpserver",
        name="ctx7",
        tag="v1",
        target="codex",
        user_id="user-1",
    )

    merge = recipe["steps"][1]
    assert merge["type"] == "merge_toml"
    assert merge["path"] == "~/.codex/config.toml"
    assert "[mcp_servers.ctx7]" in merge["content"]


@pytest.mark.asyncio
async def test_name_path_traversal_is_rejected_before_registry_call():
    registry = FakeRegistryClient(skill_resource())
    service = InstallRecipeService(registry_client=registry)

    with pytest.raises(InstallRecipeValidationError):
        await service.build(
            kind="skill",
            name="../team-skill",
            tag="v1",
            target="cursor",
            user_id="user-1",
        )

    assert registry.calls == []


@pytest.mark.asyncio
async def test_repository_subfolder_path_traversal_is_rejected():
    registry = FakeRegistryClient(skill_resource(subfolder="../outside"))
    service = InstallRecipeService(registry_client=registry)

    with pytest.raises(InstallRecipeValidationError):
        await service.build(
            kind="skill",
            name="team-skill",
            tag="v1",
            target="cursor",
            user_id="user-1",
        )


class FakeRecipeService:
    async def build(self, **kwargs):
        return {
            "version": "1",
            "resource_kind": kwargs["kind"],
            "name": kwargs["name"],
            "tag": kwargs["tag"],
            "target": kwargs["target"],
            "user_id": kwargs["user_id"],
            "resource": {},
            "source": {"type": "registry"},
            "steps": [{"id": "verify-target", "type": "verify", "path": ".cursor/skills/demo"}],
            "rollback": [{"id": "restore-backup", "type": "restore_backup", "path": ".cursor/skills/demo"}],
        }


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "enforce")
    app = FastAPI()
    app.add_middleware(AuthMiddleware, mode="enforce", token_to_team={"team-token": "dev"})
    app.include_router(store_router)
    app.dependency_overrides[get_install_recipe_service] = lambda: FakeRecipeService()
    return app


@pytest.mark.asyncio
async def test_install_recipe_endpoint_returns_steps_and_rollback(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "team-token"},
    ) as client:
        response = await client.post(
            "/api/v1/store/install-recipes",
            json={"kind": "skill", "name": "demo", "tag": "v1", "target": "cursor"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "team:dev"
    assert body["steps"][0]["type"] == "verify"
    assert body["rollback"][0]["type"] == "restore_backup"


@pytest.mark.asyncio
async def test_install_recipe_endpoint_rejects_invalid_kind_with_422(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": "team-token"},
    ) as client:
        response = await client.post(
            "/api/v1/store/install-recipes",
            json={"kind": "model", "name": "demo", "tag": "v1", "target": "cursor"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_install_recipe_endpoint_without_auth_is_denied(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/store/install-recipes",
            json={"kind": "skill", "name": "demo", "tag": "v1", "target": "cursor"},
        )

    assert response.status_code == 401
