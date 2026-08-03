#!/usr/bin/env python3
"""Seed local mem0 skills into an AgentRegistry catalog.

The current AgentRegistry Skill schema supports title/description and an
optional repository source. It does not yet expose an inline content field, so
this script preserves the SKILL.md body in metadata.annotations while filling
the official Skill fields for catalog listing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_REGISTRY_URL = "http://127.0.0.1:8765/registry-api"
DEFAULT_TOKEN = "local"
DEFAULT_NAMESPACE = "default"
DEFAULT_TAG = "latest"

ANNOTATION_PREFIX = "agentregistry.mem0.ai"
CONTENT_ANNOTATION = f"{ANNOTATION_PREFIX}/skill-md"
SOURCE_PATH_ANNOTATION = f"{ANNOTATION_PREFIX}/source-path"
FRONTMATTER_ANNOTATION = f"{ANNOTATION_PREFIX}/frontmatter-json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_skills_dir() -> Path:
    return repo_root() / "skills"


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}

    frontmatter = lines[1:end]
    parsed: dict[str, Any] = {}
    index = 0
    while index < len(frontmatter):
        raw = frontmatter[index]
        if not raw.strip() or raw.startswith((" ", "\t")) or ":" not in raw:
            index += 1
            continue

        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in {">", "|"}:
            block_lines: list[str] = []
            index += 1
            while index < len(frontmatter):
                candidate = frontmatter[index]
                if candidate.strip() and not candidate.startswith((" ", "\t")):
                    break
                block_lines.append(candidate.strip())
                index += 1
            if value == ">":
                parsed[key] = " ".join(part for part in block_lines if part)
            else:
                parsed[key] = "\n".join(block_lines)
            continue

        parsed[key] = strip_quotes(value)
        index += 1

    return parsed


def skill_body_without_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).lstrip("\n")
    return text


def first_markdown_heading(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                return heading
    return None


def dns_name(value: str) -> str:
    name = value.strip().lower()
    name = re.sub(r"[^a-z0-9.-]+", "-", name)
    name = re.sub(r"-+", "-", name)
    name = re.sub(r"\.+", ".", name)
    name = name.strip("-.")
    if not name:
        raise ValueError(f"cannot derive DNS name from {value!r}")
    if len(name) > 253:
        name = name[:253].strip("-.")
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?(\.[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?)*", name):
        raise ValueError(f"derived skill name is not a DNS-1123 subdomain: {name!r}")
    return name


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_block(value: str, indent: int) -> str:
    spaces = " " * indent
    if value == "":
        return spaces + '""'
    lines = value.splitlines()
    if value.endswith("\n"):
        lines.append("")
    return "|-\n" + "\n".join(f"{spaces}{line}" for line in lines)


def build_skill_doc(skill_path: Path, skills_dir: Path, namespace: str, tag: str) -> tuple[str, str]:
    text = skill_path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    body = skill_body_without_frontmatter(text)

    folder_name = skill_path.parent.name
    raw_name = str(frontmatter.get("name") or folder_name)
    name = dns_name(raw_name)
    title = first_markdown_heading(body) or raw_name
    description = str(frontmatter.get("description") or f"{title} skill")
    rel_path = skill_path.relative_to(repo_root()).as_posix()

    annotations = {
        SOURCE_PATH_ANNOTATION: rel_path,
        FRONTMATTER_ANNOTATION: json.dumps(frontmatter, ensure_ascii=False, sort_keys=True),
        CONTENT_ANNOTATION: text,
    }

    lines = [
        "apiVersion: ar.dev/v1alpha1",
        "kind: Skill",
        "metadata:",
        f"  namespace: {yaml_scalar(namespace)}",
        f"  name: {yaml_scalar(name)}",
        f"  tag: {yaml_scalar(tag)}",
        "  labels:",
        '    app.kubernetes.io/part-of: "mem0-shared"',
        '    agentregistry.mem0.ai/source: "seed-script"',
        "  annotations:",
    ]
    for key, value in annotations.items():
        rendered = yaml_block(value, 6)
        if rendered.startswith("|"):
            lines.append(f"    {key}: {rendered}")
        else:
            lines.append(f"    {key}: {rendered.strip()}")

    lines.extend(
        [
            "spec:",
            f"  title: {yaml_scalar(title)}",
            f"  description: {yaml_block(description, 4)}",
        ]
    )
    return name, "\n".join(lines) + "\n"


def discover_skill_files(skills_dir: Path) -> list[Path]:
    if not skills_dir.is_dir():
        raise FileNotFoundError(f"skills directory not found: {skills_dir}")
    return sorted(path for path in skills_dir.glob("*/SKILL.md") if path.is_file())


def request_json(method: str, url: str, token: str, body: bytes | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/yaml"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc
    if not data:
        return {}
    return json.loads(data.decode("utf-8"))


def endpoint(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v0"):
        base = base[:-3]
    return base + path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-url", default=DEFAULT_REGISTRY_URL, help="AgentRegistry base URL")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Bearer token for the registry")
    parser.add_argument("--skills-dir", type=Path, default=default_skills_dir(), help="Directory containing */SKILL.md")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE, help="Skill namespace to publish")
    parser.add_argument("--tag", default=DEFAULT_TAG, help="Skill tag to publish")
    parser.add_argument("--dry-run", action="store_true", help="Validate via dryRun=true without mutating the registry")
    parser.add_argument("--print-yaml", action="store_true", help="Print generated multi-document YAML and exit")
    args = parser.parse_args()

    skill_files = discover_skill_files(args.skills_dir)
    docs: list[str] = []
    names: list[str] = []
    for skill_file in skill_files:
        name, doc = build_skill_doc(skill_file, args.skills_dir, args.namespace, args.tag)
        names.append(name)
        docs.append(doc)

    payload = "---\n".join(docs).encode("utf-8")
    if args.print_yaml:
        sys.stdout.write(payload.decode("utf-8"))
        return 0

    apply_url = endpoint(args.registry_url, "/v0/apply")
    if args.dry_run:
        apply_url += "?dryRun=true"

    apply_response = request_json("POST", apply_url, args.token, payload)
    results = apply_response.get("results", [])
    failures = [result for result in results if result.get("status") == "failed"]
    successful = [result for result in results if result.get("status") != "failed"]

    list_response: dict[str, Any] = {}
    listed_names: set[str] = set()
    if not args.dry_run:
        list_url = endpoint(args.registry_url, "/v0/skills")
        list_response = request_json("GET", list_url, args.token)
        listed_names = {item.get("metadata", {}).get("name", "") for item in list_response.get("items", [])}

    missing_after_publish = sorted(set(names) - listed_names) if not args.dry_run else []

    summary = {
        "skills_dir": str(args.skills_dir),
        "namespace": args.namespace,
        "tag": args.tag,
        "discovered": len(skill_files),
        "applied": len(successful),
        "failed": len(failures),
        "sample_names": names[:10],
        "failures": failures,
        "missing_after_publish": missing_after_publish,
        "listed_count": len(list_response.get("items", [])) if list_response else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if failures or missing_after_publish:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
