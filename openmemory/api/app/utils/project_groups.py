"""Grouping of related project names for the read path.

``project`` is derived from the working directory of the session, but real work
crosses repositories: the same task touches the Delphi app, the modular DLL and
the database repo. The store therefore ends up with the same subject spread over
``sysmovs``, ``sysmos1-modular``, ``db-sysmo-s1`` and ``default``, and the project
ranking hint only ever rewards the one directory the agent happened to be in.

A group maps sibling project names to a shared label, so:

- the soft hint boosts the whole family, not just the exact directory;
- ``strict_project`` narrows to the family instead of a single repo, which is
  what a user asking for "this project" actually means.

Reads stay global either way — this only affects ranking and the opt-in filter.

Configured via MEM0_PROJECT_GROUPS, as ``group=member,member;group2=member``::

    MEM0_PROJECT_GROUPS="sysmo-s1=sysmovs,sysmos1-modular,db-sysmo-s1"

Unlisted projects keep behaving exactly as before.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from app.utils.recency import normalize_project_name

_lock = threading.Lock()
_cache: Optional[tuple[dict[str, str], dict[str, list[str]]]] = None
_cache_raw: Optional[str] = None


def _parse(raw: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Parse the env format into lookup structures.

    Returns ``({normalized member -> group label}, {group label -> member names})``.
    Member names are kept VERBATIM in the second map: they are matched against the
    ``project`` payload stored in Qdrant, which holds the name as written, not the
    normalized form used for comparison.
    """
    mapping: dict[str, str] = {}
    members_by_label: dict[str, list[str]] = {}
    for chunk in (raw or "").split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        label, members = chunk.split("=", 1)
        label = label.strip()
        if not label:
            continue
        # The label is a member of its own group, so naming the group directly works.
        for member in [label, *members.split(",")]:
            member = member.strip()
            key = normalize_project_name(member)
            if not key:
                continue
            mapping[key] = label
            bucket = members_by_label.setdefault(label, [])
            if member not in bucket:
                bucket.append(member)
    return mapping, members_by_label


def _parsed() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Parsed configuration, rebuilt when the env value changes."""
    global _cache, _cache_raw
    raw = os.getenv("MEM0_PROJECT_GROUPS", "") or ""
    if _cache is not None and _cache_raw == raw:
        return _cache
    with _lock:
        _cache = _parse(raw)
        _cache_raw = raw
    return _cache


def project_group_map() -> dict[str, str]:
    """``{normalized project name -> group label}``."""
    return _parsed()[0]


def reset_project_group_cache() -> None:
    """Drop the parsed configuration (tests / config reload)."""
    global _cache, _cache_raw
    with _lock:
        _cache = None
        _cache_raw = None


def resolve_project_group(project) -> Optional[str]:
    """Group label for ``project``, or None when it belongs to no group."""
    key = normalize_project_name(project)
    if not key:
        return None
    return project_group_map().get(key)


def projects_in_group(label) -> list[str]:
    """Every configured member name of ``label``'s group, the label included.

    Names come back exactly as written in the configuration — they are matched
    against the ``project`` payload in the vector store, so the normalized form
    used for comparison would never match anything.
    """
    target = resolve_project_group(label)
    if not target:
        return []
    return sorted(_parsed()[1].get(target, []))


def same_project_family(a, b) -> bool:
    """True when both names resolve to the same configured group."""
    group_a = resolve_project_group(a)
    return bool(group_a) and group_a == resolve_project_group(b)
