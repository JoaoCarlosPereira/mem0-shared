#!/usr/bin/env python3
"""Embed local ``.docs/tasks/<slug>/adrs/*.md`` into the Shared TechSpec.

Legacy TechSpecs only store one-line links to ``adrs/adr-NNN.md``. Those files
never reach the Shared UI (404). This one-shot backfills the ADR section with
the full local markdown when the files still exist on disk.

Usage:
  python openmemory/scripts/backfill-techspec-adrs.py \\
    --slug autenticacao-google-identidade \\
    --project mem0-shared \\
    --docs-root .docs/tasks \\
    --api http://localhost:8765

Dry-run (no write):
  ... --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SECTION_RE = re.compile(
    r"(^##\s+Registros de Decisão de Arquitetura\s*$)",
    re.IGNORECASE | re.MULTILINE,
)
ADR_FILE_RE = re.compile(r"^adr-(\d{3})\.md$", re.IGNORECASE)
NEXT_H2_RE = re.compile(r"^##\s+\S", re.MULTILINE)


def _get(url: str) -> dict:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _put(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_local_adrs(adrs_dir: Path) -> list[tuple[int, str]]:
    items: list[tuple[int, str]] = []
    if not adrs_dir.is_dir():
        raise FileNotFoundError(f"ADR directory not found: {adrs_dir}")
    for path in sorted(adrs_dir.iterdir()):
        m = ADR_FILE_RE.match(path.name)
        if not m or not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8").strip()
        # Demote top-level ADR title so it nests under the TechSpec H2 section.
        body = re.sub(r"^#\s+(ADR-\d{3}:)", r"### \1", raw, count=1, flags=re.I)
        items.append((int(m.group(1)), body))
    if not items:
        raise RuntimeError(f"No adr-NNN.md files in {adrs_dir}")
    return items


def replace_adr_section(techspec: str, adr_bodies: list[str]) -> str:
    m = SECTION_RE.search(techspec)
    if not m:
        raise RuntimeError(
            'TechSpec missing "## Registros de Decisão de Arquitetura" section'
        )
    start = m.start()
    # End at next H2 after the section heading, or EOF.
    rest = techspec[m.end() :]
    next_h2 = NEXT_H2_RE.search(rest)
    end = m.end() + next_h2.start() if next_h2 else len(techspec)

    intro = (
        "## Registros de Decisão de Arquitetura\n\n"
        "ADRs técnicos embutidos a partir dos arquivos locais "
        "(backfill Shared — texto completo; sem links `adrs/*.md`).\n\n"
    )
    block = intro + "\n\n".join(adr_bodies) + ("\n" if not next_h2 else "\n\n")
    return techspec[:start] + block + techspec[end:]


def find_workspace(api: str, project: str, slug: str) -> dict:
    items = _get(f"{api.rstrip('/')}/api/v1/specs/workspaces")
    if isinstance(items, dict):
        items = items.get("items") or items.get("workspaces") or []
    for w in items:
        if w.get("slug") == slug and (
            not project or w.get("project_id") == project
        ):
            return w
    raise RuntimeError(f"Workspace not found: project={project!r} slug={slug!r}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--slug", required=True)
    p.add_argument("--project", default="")
    p.add_argument("--docs-root", type=Path, default=Path(".docs/tasks"))
    p.add_argument("--api", default="http://localhost:8765")
    p.add_argument("--author", default="backfill-techspec-adrs")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    adrs_dir = args.docs_root / args.slug / "adrs"
    adrs = load_local_adrs(adrs_dir)
    print(f"loaded {len(adrs)} ADRs from {adrs_dir}")

    ws = find_workspace(args.api, args.project, args.slug)
    wid = ws["id"]
    print(f"workspace {wid} project={ws.get('project_id')} slug={ws.get('slug')}")

    board = _get(f"{args.api.rstrip('/')}/api/v1/specs/workspaces/{wid}")
    tech = None
    version = None
    for doc in board.get("documents") or []:
        if doc.get("document_type") == "techspec":
            tech = doc.get("current_content") or ""
            version = doc.get("current_version")
            break
    if tech is None:
        raise RuntimeError("No techspec document on workspace")

    new_content = replace_adr_section(tech, [body for _, body in adrs])
    link_count = len(re.findall(r"\]\(adrs/[^)]+\)", new_content))
    print(
        f"techspec v{version}: {len(tech)} → {len(new_content)} chars; "
        f"remaining adrs/ links: {link_count}"
    )

    if args.dry_run:
        print("dry-run: not writing")
        return 0

    url = (
        f"{args.api.rstrip('/')}/api/v1/specs/workspaces/{wid}/documents/techspec"
    )
    try:
        result = _put(
            url,
            {
                "content": new_content,
                "expected_version": version,
                "author": args.author,
            },
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"PUT failed {exc.code}: {body}", file=sys.stderr)
        return 1

    print(json.dumps({"ok": True, "version": result.get("version"), "conflict": result.get("conflict")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
