#!/usr/bin/env python3
"""Inject read-audit hooks into MCP server and admin router (root-owned files)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP = ROOT / "api" / "app" / "mcp_server.py"
ADMIN = ROOT / "api" / "app" / "routers" / "admin.py"
MEMORIES = ROOT / "api" / "app" / "routers" / "memories.py"

MCP_SEARCH_HOOK = '''
        from app.utils.read_audit import record_memory_reads
        record_memory_reads(
            project=project,
            memory_ids=[r.get("id") for r in results],
            access_type="search",
            source="mcp",
            hostname=resolve_hostname(user_id_var.get(None)),
            client_name=client_name_var.get(None) or DEFAULT_CLIENT_NAME,
            query=query,
            items=results,
        )

        return json.dumps({"results": results}, indent=2)'''

MCP_LIST_HOOK = '''
        from app.utils.read_audit import record_memory_reads
        record_memory_reads(
            project=project,
            memory_ids=[r.get("id") for r in results],
            access_type="list",
            source="mcp",
            hostname=resolve_hostname(user_id_var.get(None)),
            client_name=client_name_var.get(None) or DEFAULT_CLIENT_NAME,
            items=results,
        )

        return json.dumps({"results": results}, indent=2)'''

ADMIN_HOOK = '''
    from app.utils.read_audit import record_memory_reads

    record_memory_reads(
        project=project,
        memory_ids=[item.get("id") for item in items],
        access_type="search" if search else "list",
        source="admin",
        query=search,
        items=[{"id": i.get("id"), "project": project, "metadata": {"project": project}} for i in items],
    )

    return {"items": items, "total": len(items)}'''


def patch_file(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text()
    if new.strip() in text:
        print(f"skip {label}: already patched")
        return True
    if old not in text:
        print(f"FAIL {label}: anchor not found", file=sys.stderr)
        return False
    path.write_text(text.replace(old, new, 1))
    print(f"patched {label}")
    return True


def patch_memories_get(path: Path) -> bool:
    text = path.read_text()
    needle = "    if shared:\n        return shared"
    insert = """    if shared:
        from app.utils.read_audit import record_memory_reads

        project = (shared.get("metadata_") or {}).get("project") or shared.get("app_name")
        record_memory_reads(
            project=str(project) if project else None,
            memory_ids=[str(memory_id)],
            access_type="get",
            source="api",
            items=[{"id": str(memory_id), "project": project, "metadata_": shared.get("metadata_")}],
        )
        return shared"""
    if insert in text:
        print("skip memories get: already patched")
        return True
    if needle not in text:
        print("FAIL memories get: anchor not found", file=sys.stderr)
        return False
    path.write_text(text.replace(needle, insert, 1))
    print("patched memories get")
    return True


def main() -> int:
    ok = True
    ok &= patch_file(
        MCP,
        '        return json.dumps({"results": results}, indent=2)\n    except Exception as e:\n        logging.exception(e)\n        return f"Error searching memory: {e}"',
        MCP_SEARCH_HOOK + '\n    except Exception as e:\n        logging.exception(e)\n        return f"Error searching memory: {e}"',
        "mcp search_memory",
    )
    ok &= patch_file(
        MCP,
        '        return json.dumps({"results": results}, indent=2)\n    except Exception as e:\n        logging.exception(f"Error getting memories: {e}")',
        MCP_LIST_HOOK + '\n    except Exception as e:\n        logging.exception(f"Error getting memories: {e}")',
        "mcp list_memories",
    )
    ok &= patch_file(
        ADMIN,
        '    return {"items": items, "total": len(items)}',
        ADMIN_HOOK,
        "admin project memories",
    )
    ok &= patch_memories_get(MEMORIES)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
