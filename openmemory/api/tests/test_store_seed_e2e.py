"""task_08 store seed flow tests.

Local live E2E (optional, requires running OpenMemory + AgentRegistry):

    RUN_STORE_E2E=1 \
    STORE_E2E_REGISTRY_URL=http://127.0.0.1:8765/registry-api \
    STORE_E2E_TOKEN=local \
    pytest tests/test_store_seed_e2e.py

Without ``RUN_STORE_E2E=1`` this file still validates the publish -> discover
-> install path against an in-memory registry, so CI does not require the live
registry service.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.services.store_recipes import InstallRecipeService
from app.utils.agentregistry import AgentRegistryHttpClient, AgentRegistryResourceNotFound
from tests.helpers.store_recipe_apply import RecipeApplyError, apply_recipe

SKILL_NAME = "mem0-e2e-skill"
MCP_NAME = "mem0-e2e-mcp"
TAG = "task-08"
TARGETS = ("cursor", "claude", "codex")


class InMemoryRegistryClient:
    def __init__(self):
        self.resources: dict[tuple[str, str, str], dict[str, Any]] = {}

    async def apply_resource(self, *, resource, dry_run=False, auth_headers=None):
        metadata = resource["metadata"]
        key = (_catalog_kind(resource["kind"]), metadata["name"], metadata.get("tag") or "latest")
        if not dry_run:
            self.resources[key] = copy.deepcopy(resource)
        return {
            "results": [
                {
                    "apiVersion": resource.get("apiVersion"),
                    "kind": resource.get("kind"),
                    "name": metadata["name"],
                    "tag": metadata.get("tag") or "latest",
                    "status": "configured" if key in self.resources else "created",
                }
            ]
        }

    async def list_resources(self, *, kind, namespace="default", limit=20, cursor=None, auth_headers=None):
        items = [
            copy.deepcopy(resource)
            for (stored_kind, _, _), resource in sorted(self.resources.items())
            if stored_kind == kind and resource.get("metadata", {}).get("namespace", "default") == namespace
        ]
        return {"items": items[:limit], "nextCursor": ""}

    async def get_resource(self, *, kind, name, tag, auth_headers=None):
        try:
            return copy.deepcopy(self.resources[(kind, name, tag)])
        except KeyError as exc:
            raise AgentRegistryResourceNotFound() from exc


def seed_resources() -> list[dict[str, Any]]:
    return [_skill_seed(), _mcp_seed()]


@pytest.mark.asyncio
async def test_mocked_seed_publish_discover_install_all_targets(tmp_path):
    registry = InMemoryRegistryClient()
    for resource in seed_resources():
        result = await registry.apply_resource(resource=resource)
        assert result["results"][0]["status"] in {"created", "configured"}

    skill_list = await registry.list_resources(kind="skill")
    mcp_list = await registry.list_resources(kind="mcpserver")
    assert _names(skill_list) == {SKILL_NAME}
    assert _names(mcp_list) == {MCP_NAME}
    skill = await registry.get_resource(kind="skill", name=SKILL_NAME, tag=TAG)
    assert skill["metadata"]["name"] == SKILL_NAME

    service = InstallRecipeService(registry_client=registry)
    for target in TARGETS:
        repo_root = tmp_path / target / "repo"
        home_root = tmp_path / target / "home"
        repo_root.mkdir(parents=True)
        home_root.mkdir(parents=True)

        skill_recipe = await service.build(
            kind="skill",
            name=SKILL_NAME,
            tag=TAG,
            target=target,
            user_id="test-user",
        )
        mcp_recipe = await service.build(
            kind="mcpserver",
            name=MCP_NAME,
            tag=TAG,
            target=target,
            user_id="test-user",
        )

        apply_recipe(skill_recipe, repo_root=repo_root, home_root=home_root)
        apply_recipe(mcp_recipe, repo_root=repo_root, home_root=home_root)
        first_snapshot = _target_snapshot(repo_root, home_root)

        apply_recipe(skill_recipe, repo_root=repo_root, home_root=home_root)
        apply_recipe(mcp_recipe, repo_root=repo_root, home_root=home_root)
        assert _target_snapshot(repo_root, home_root) == first_snapshot

        _assert_skill_installed(target, repo_root, home_root)
        _assert_mcp_installed(target, repo_root, home_root)

        apply_recipe(mcp_recipe, repo_root=repo_root, home_root=home_root, rollback=True)
        apply_recipe(skill_recipe, repo_root=repo_root, home_root=home_root, rollback=True)
        assert not _skill_path(target, repo_root, home_root).exists()
        assert not _mcp_path(target, repo_root, home_root).exists()


@pytest.mark.asyncio
async def test_apply_recipe_restores_existing_backup_in_tmpdir(tmp_path):
    registry = InMemoryRegistryClient()
    await registry.apply_resource(resource=_skill_seed())
    service = InstallRecipeService(registry_client=registry)
    recipe = await service.build(
        kind="skill",
        name=SKILL_NAME,
        tag=TAG,
        target="cursor",
        user_id="test-user",
    )

    repo_root = tmp_path / "repo"
    home_root = tmp_path / "home"
    original = repo_root / ".cursor" / "skills" / SKILL_NAME / "SKILL.md"
    original.parent.mkdir(parents=True)
    original.write_text("# Old Skill\n", encoding="utf-8")

    apply_recipe(recipe, repo_root=repo_root, home_root=home_root)
    assert "Task 08 test skill" in original.read_text(encoding="utf-8")

    apply_recipe(recipe, repo_root=repo_root, home_root=home_root)
    apply_recipe(recipe, repo_root=repo_root, home_root=home_root, rollback=True)
    assert original.read_text(encoding="utf-8") == "# Old Skill\n"


def test_apply_recipe_rejects_path_traversal(tmp_path):
    recipe = {
        "steps": [
            {
                "id": "backup-escape",
                "type": "backup",
                "path": "../outside",
            }
        ],
        "rollback": [],
    }

    with pytest.raises(RecipeApplyError, match="escapes sandbox"):
        apply_recipe(recipe, repo_root=tmp_path / "repo", home_root=tmp_path / "home")


@pytest.mark.skipif(
    os.getenv("RUN_STORE_E2E") != "1",
    reason="set RUN_STORE_E2E=1 to hit live AgentRegistry",
)
@pytest.mark.asyncio
async def test_live_agentregistry_seed_discover_install_recipes_tmpdir(tmp_path):
    registry_url = os.getenv("STORE_E2E_REGISTRY_URL", "http://127.0.0.1:8765/registry-api")
    token = os.getenv("STORE_E2E_TOKEN", "local")
    auth_headers = {"Authorization": f"Bearer {token}"}
    registry = AgentRegistryHttpClient(base_url=registry_url)

    try:
        for resource in seed_resources():
            await registry.apply_resource(resource=resource, auth_headers=auth_headers)

        skill_list = await registry.list_resources(kind="skill", limit=100, auth_headers=auth_headers)
        mcp_list = await registry.list_resources(kind="mcpserver", limit=100, auth_headers=auth_headers)
        assert SKILL_NAME in _names(skill_list)
        assert MCP_NAME in _names(mcp_list)

        service = InstallRecipeService(registry_client=registry)
        for target in TARGETS:
            repo_root = tmp_path / target / "repo"
            home_root = tmp_path / target / "home"
            repo_root.mkdir(parents=True)
            home_root.mkdir(parents=True)
            recipe = await service.build(
                kind="skill",
                name=SKILL_NAME,
                tag=TAG,
                target=target,
                user_id="live-e2e",
                auth_headers=auth_headers,
            )
            apply_recipe(recipe, repo_root=repo_root, home_root=home_root)
            _assert_skill_installed(target, repo_root, home_root)
    except Exception as exc:
        pytest.fail(
            f"Live store E2E failed against {registry_url}. "
            "Ensure AgentRegistry is running and accepts the configured token. "
            f"Original error: {exc}"
        )


def _skill_seed() -> dict[str, Any]:
    skill_md = """---
name: mem0-e2e-skill
description: Skill fixture for task_08 store E2E.
---

# Task 08 test skill

Use this fixture to validate publish, discovery and install recipes.
"""
    return {
        "apiVersion": "ar.dev/v1alpha1",
        "kind": "Skill",
        "metadata": {
            "namespace": "default",
            "name": SKILL_NAME,
            "tag": TAG,
            "labels": {
                "app.kubernetes.io/part-of": "mem0-shared",
                "agentregistry.mem0.ai/source": "test-seed",
            },
            "annotations": {
                "agentregistry.mem0.ai/skill-md": skill_md,
                "agentregistry.mem0.ai/source-path": "openmemory/api/tests/test_store_seed_e2e.py",
            },
        },
        "spec": {
            "title": "Task 08 Test Skill",
            "description": "Skill fixture for task_08 store E2E.",
        },
    }


def _mcp_seed() -> dict[str, Any]:
    return {
        "apiVersion": "ar.dev/v1alpha1",
        "kind": "MCPServer",
        "metadata": {
            "namespace": "default",
            "name": MCP_NAME,
            "tag": TAG,
            "labels": {
                "app.kubernetes.io/part-of": "mem0-shared",
                "agentregistry.mem0.ai/source": "test-seed",
            },
        },
        "spec": {
            "title": "Task 08 Test MCP",
            "description": "Remote MCP fixture for task_08 store E2E.",
            "remote": {
                "type": "http",
                "url": "http://127.0.0.1:8765/mcp/cursor/http/Mini-PC",
            },
        },
    }


def _catalog_kind(registry_kind: str) -> str:
    return {"Skill": "skill", "MCPServer": "mcpserver"}[registry_kind]


def _names(response: dict[str, Any]) -> set[str]:
    return {item.get("metadata", {}).get("name", "") for item in response.get("items", [])}


def _skill_path(target: str, repo_root: Path, home_root: Path) -> Path:
    if target == "cursor":
        return repo_root / ".cursor" / "skills" / SKILL_NAME / "SKILL.md"
    return home_root / f".{target}" / "skills" / SKILL_NAME / "SKILL.md"


def _mcp_path(target: str, repo_root: Path, home_root: Path) -> Path:
    if target == "cursor":
        return repo_root / ".cursor" / "mcp.json"
    if target == "claude":
        return repo_root / ".mcp.json"
    return home_root / ".codex" / "config.toml"


def _assert_skill_installed(target: str, repo_root: Path, home_root: Path) -> None:
    content = _skill_path(target, repo_root, home_root).read_text(encoding="utf-8")
    assert "# Task 08 test skill" in content
    assert "mem0-e2e-skill" in content


def _assert_mcp_installed(target: str, repo_root: Path, home_root: Path) -> None:
    path = _mcp_path(target, repo_root, home_root)
    content = path.read_text(encoding="utf-8")
    if target == "codex":
        assert f"[mcp_servers.{MCP_NAME}]" in content
        assert "http://127.0.0.1:8765/mcp/cursor/http/Mini-PC" in content
        return

    data = json.loads(content)
    assert (
        data["mcpServers"][MCP_NAME]["url"]
        == "http://127.0.0.1:8765/mcp/cursor/http/Mini-PC"
    )


def _target_snapshot(repo_root: Path, home_root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for root_name, root in (("repo", repo_root), ("home", home_root)):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snapshot[f"{root_name}/{path.relative_to(root).as_posix()}"] = path.read_text(
                    encoding="utf-8"
                )
    return snapshot
