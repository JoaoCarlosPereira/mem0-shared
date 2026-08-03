"""Apply OpenMemory store install recipes inside an isolated test sandbox.

This helper models the host-side part of the install flow without touching the
developer's real repository or home directory. It intentionally supports only
the declarative step types emitted by ``InstallRecipeService``.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

CONTENT_ANNOTATION = "agentregistry.mem0.ai/skill-md"
BACKUP_DIR_NAME = ".store-recipe-backups"


class RecipeApplyError(AssertionError):
    """Raised when a recipe step cannot be applied in the sandbox."""


def apply_recipe(
    recipe: dict[str, Any],
    *,
    repo_root: Path,
    home_root: Path,
    rollback: bool = False,
) -> list[str]:
    """Apply or roll back a recipe using ``repo_root`` and ``home_root``.

    Paths starting with ``~/`` are resolved below ``home_root``; all other
    relative paths are resolved below ``repo_root``. Absolute paths and path
    traversal are rejected so tests cannot escape their tmpdir.
    """

    applied: list[str] = []
    steps: Iterable[dict[str, Any]] = recipe.get("rollback" if rollback else "steps") or []
    for step in steps:
        step_type = step.get("type")
        if step_type == "backup":
            _backup_path(step["path"], repo_root=repo_root, home_root=home_root)
        elif step_type == "copy":
            _copy_resource(recipe, step, repo_root=repo_root, home_root=home_root)
        elif step_type == "merge_json":
            _merge_json(step, repo_root=repo_root, home_root=home_root)
        elif step_type == "merge_toml":
            _merge_toml(step, repo_root=repo_root, home_root=home_root)
        elif step_type == "verify":
            _verify(step, repo_root=repo_root, home_root=home_root)
        elif step_type == "restore_backup":
            _restore_backup(step, repo_root=repo_root, home_root=home_root)
        else:
            raise RecipeApplyError(f"Unsupported recipe step type: {step_type!r}")
        applied.append(str(step.get("id") or step_type))
    return applied


def _copy_resource(recipe: dict[str, Any], step: dict[str, Any], *, repo_root: Path, home_root: Path) -> None:
    target = _resolve_sandbox_path(step["to"], repo_root=repo_root, home_root=home_root)
    content = _resource_content(recipe, step)
    kind = recipe.get("resource_kind")

    if kind in {"skill", "plugin"}:
        target.mkdir(parents=True, exist_ok=True)
        filename = "SKILL.md" if kind == "skill" else "RESOURCE.json"
        (target / filename).write_text(content, encoding="utf-8")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _resource_content(recipe: dict[str, Any], step: dict[str, Any]) -> str:
    if isinstance(step.get("content"), str):
        return step["content"]

    resource = recipe.get("resource") if isinstance(recipe.get("resource"), dict) else {}
    metadata = resource.get("metadata") if isinstance(resource.get("metadata"), dict) else {}
    annotations = metadata.get("annotations") if isinstance(metadata.get("annotations"), dict) else {}
    if isinstance(annotations.get(CONTENT_ANNOTATION), str):
        return annotations[CONTENT_ANNOTATION]

    return json.dumps(resource or {"source": step.get("from")}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _merge_json(step: dict[str, Any], *, repo_root: Path, home_root: Path) -> None:
    path = _resolve_sandbox_path(step["path"], repo_root=repo_root, home_root=home_root)
    current: dict[str, Any] = {}
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RecipeApplyError(f"Invalid JSON before merge: {path}") from exc
        if not isinstance(parsed, dict):
            raise RecipeApplyError(f"JSON config must be an object: {path}")
        current = parsed

    _deep_merge(current, step.get("content") or {})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _merge_toml(step: dict[str, Any], *, repo_root: Path, home_root: Path) -> None:
    path = _resolve_sandbox_path(step["path"], repo_root=repo_root, home_root=home_root)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    merged = _replace_toml_section(existing, step["key"], str(step.get("content") or ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(merged, encoding="utf-8")


def _verify(step: dict[str, Any], *, repo_root: Path, home_root: Path) -> None:
    path = _resolve_sandbox_path(step["path"], repo_root=repo_root, home_root=home_root)
    for check in step.get("checks") or []:
        check_type = check.get("type")
        if check_type == "exists":
            if not path.exists():
                raise RecipeApplyError(f"Expected recipe path to exist: {path}")
        elif check_type == "resource_name":
            expected = str(check.get("value") or "")
            if path.name != expected and expected not in _read_text_tree(path):
                raise RecipeApplyError(f"Expected resource name {expected!r} in {path}")
        elif check_type == "config_key":
            if not _config_key_exists(path, str(check.get("key") or "")):
                raise RecipeApplyError(f"Expected config key {check.get('key')!r} in {path}")
        else:
            raise RecipeApplyError(f"Unsupported verify check type: {check_type!r}")


def _backup_path(logical_path: str, *, repo_root: Path, home_root: Path) -> None:
    target = _resolve_sandbox_path(logical_path, repo_root=repo_root, home_root=home_root)
    state_dir = _backup_state_dir(logical_path, repo_root)
    metadata_path = state_dir / "metadata.json"
    if metadata_path.exists():
        return

    state_dir.mkdir(parents=True, exist_ok=True)
    payload = state_dir / "payload"
    metadata: dict[str, Any] = {"path": logical_path, "existed": target.exists(), "kind": None}
    if target.exists():
        if target.is_dir():
            metadata["kind"] = "dir"
            shutil.copytree(target, payload)
        else:
            metadata["kind"] = "file"
            shutil.copy2(target, payload)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _restore_backup(step: dict[str, Any], *, repo_root: Path, home_root: Path) -> None:
    logical_path = step["path"]
    state_dir = _backup_state_dir(logical_path, repo_root)
    metadata_path = state_dir / "metadata.json"
    if not metadata_path.exists():
        if step.get("if_backup_exists"):
            return
        raise RecipeApplyError(f"Missing backup for {logical_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    target = _resolve_sandbox_path(metadata["path"], repo_root=repo_root, home_root=home_root)
    _remove_path(target)
    if metadata.get("existed"):
        payload = state_dir / "payload"
        if metadata.get("kind") == "dir":
            shutil.copytree(payload, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(payload, target)
    shutil.rmtree(state_dir)


def _resolve_sandbox_path(logical_path: str, *, repo_root: Path, home_root: Path) -> Path:
    if not isinstance(logical_path, str) or not logical_path.strip():
        raise RecipeApplyError("Recipe path is required")
    if logical_path.startswith("~/"):
        root = home_root.resolve()
        relative = logical_path[2:]
    else:
        path = Path(logical_path)
        if path.is_absolute() or logical_path.startswith("~"):
            raise RecipeApplyError(f"Unsafe absolute recipe path: {logical_path}")
        root = repo_root.resolve()
        relative = logical_path

    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RecipeApplyError(f"Recipe path escapes sandbox: {logical_path}") from exc
    return resolved


def _backup_state_dir(logical_path: str, repo_root: Path) -> Path:
    digest = hashlib.sha256(logical_path.encode("utf-8")).hexdigest()[:16]
    return repo_root / BACKUP_DIR_NAME / digest


def _deep_merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _replace_toml_section(existing: str, key: str, replacement: str) -> str:
    header = f"[{key}]"
    lines = existing.splitlines()
    start = next((index for index, line in enumerate(lines) if line.strip() == header), None)
    replacement_lines = replacement.rstrip("\n").splitlines()
    if start is None:
        prefix = existing.rstrip("\n")
        separator = "\n\n" if prefix else ""
        return f"{prefix}{separator}{replacement.rstrip()}\n"

    end = start + 1
    while end < len(lines) and not lines[end].lstrip().startswith("["):
        end += 1
    merged_lines = [*lines[:start], *replacement_lines, *lines[end:]]
    return "\n".join(merged_lines).rstrip("\n") + "\n"


def _read_text_tree(path: Path) -> str:
    if path.is_file():
        return path.read_text(encoding="utf-8")
    if path.is_dir():
        return "\n".join(
            child.read_text(encoding="utf-8")
            for child in sorted(path.rglob("*"))
            if child.is_file()
        )
    return ""


def _config_key_exists(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        if "." not in key and isinstance(data.get("mcpServers"), dict):
            return key in data["mcpServers"]
        current: Any = data
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        return True
    content = path.read_text(encoding="utf-8")
    return f"[{key}]" in content or f"[mcp_servers.{key}]" in content


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()
