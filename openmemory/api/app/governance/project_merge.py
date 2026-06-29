"""Detect and merge duplicate MCP projects misclassified by LLM routing."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    GovernanceJob,
    GovernancePolicy,
    GovernanceSchedule,
    PartitionTier,
    Project,
    WriteAuditLog,
    WriteQueueJob,
)
from app.utils.projects import upsert_project
from app.utils.read_cache import read_cache
from app.utils.vector_stats import count_project_memories, list_shared_memories

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_SIZE = 5
DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_BATCH_SIZE = 128


@dataclass
class ProjectProfile:
    name: str
    memory_count: int
    first_seen_hostname: Optional[str]
    samples: List[str]


@dataclass
class MergeGroup:
    canonical: str
    aliases: List[str]
    confidence: float
    reason: str


def collect_project_profiles(
    db: Session,
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> List[ProjectProfile]:
    profiles: List[ProjectProfile] = []
    for project in db.query(Project).order_by(Project.name).all():
        count = count_project_memories(project.name)
        if count <= 0:
            continue
        try:
            listing = list_shared_memories(project=project.name, page=1, size=sample_size)
            samples = [
                (item.get("content") or "")[:240]
                for item in listing.get("items", [])
                if (item.get("content") or "").strip()
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to sample memories for %s: %s", project.name, exc)
            samples = []
        profiles.append(
            ProjectProfile(
                name=project.name,
                memory_count=count,
                first_seen_hostname=project.first_seen_hostname,
                samples=samples,
            )
        )
    return profiles


def _parse_merge_groups(raw: Any, *, profiles: List[ProjectProfile]) -> List[MergeGroup]:
    known = {p.name for p in profiles}
    groups: List[MergeGroup] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        canonical = str(item.get("canonical") or "").strip()
        aliases = [
            str(a).strip()
            for a in (item.get("aliases") or [])
            if str(a).strip() and str(a).strip() != canonical
        ]
        if not canonical or not aliases:
            continue
        if canonical not in known:
            continue
        aliases = [a for a in aliases if a in known and a != canonical]
        if not aliases:
            continue
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0
        reason = str(item.get("reason") or "").strip()
        groups.append(
            MergeGroup(
                canonical=canonical,
                aliases=aliases,
                confidence=confidence,
                reason=reason,
            )
        )
    return groups


def detect_duplicate_groups_with_llm(
    profiles: List[ProjectProfile],
    llm_client,
    *,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> List[MergeGroup]:
    """Ask the LLM which catalog projects are the same real-world workspace."""
    if llm_client is None or len(profiles) < 2:
        return []

    catalog = [
        {
            "name": p.name,
            "memory_count": p.memory_count,
            "first_seen_hostname": p.first_seen_hostname,
            "sample_memories": p.samples,
        }
        for p in profiles
    ]
    prompt = (
        "You are a governance assistant for a multi-project memory system. "
        "Different project IDs sometimes refer to the SAME real software product, "
        "repository, or team workspace because an LLM or hostname heuristic "
        "misclassified writes (e.g. sysmovs, dsv-delphi-sysmovs, sysmovs-delphi).\n\n"
        "Given the project catalog JSON below, group projects that clearly represent "
        "the same workspace. Pick one canonical name per group (prefer the shortest, "
        "most general, or highest memory_count name). Only group when evidence is strong.\n\n"
        f"Catalog:\n{json.dumps(catalog, ensure_ascii=False)}\n\n"
        "Respond with JSON only:\n"
        '{"groups":[{"canonical":"name","aliases":["other"],"confidence":0.0,"reason":"..."}]}'
    )
    try:
        response = llm_client.generate_response(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM project-merge detection failed: %s", exc)
        return []

    groups = _parse_merge_groups(data.get("groups"), profiles=profiles)
    return [g for g in groups if g.confidence >= confidence_threshold]


def _pick_canonical_by_count(canonical: str, aliases: List[str]) -> str:
    counts = {canonical: count_project_memories(canonical)}
    for alias in aliases:
        counts[alias] = count_project_memories(alias)
    return max(counts, key=lambda name: (counts[name], -len(name)))


def relocate_project_memories(
    vs,
    *,
    source: str,
    target: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """Rewrite Qdrant payload.project from source to target."""
    filt = vs._create_filter({"project": source})
    offset = None
    moved = 0
    while True:
        records, offset = vs.client.scroll(
            collection_name=vs.collection_name,
            scroll_filter=filt,
            offset=offset,
            limit=batch_size,
            with_payload=True,
            with_vectors=False,
        )
        for rec in records or []:
            payload = dict(getattr(rec, "payload", {}) or {})
            payload["project"] = target
            vs.update(str(rec.id), payload=payload)
            moved += 1
        if offset is None:
            break
    return moved


def _merge_governance_schedules(db: Session, *, canonical: str, alias: str) -> None:
    """Merge alias schedule rows into canonical without PK collisions."""
    alias_rows = db.query(GovernanceSchedule).filter(GovernanceSchedule.scope == alias).all()
    for alias_row in alias_rows:
        canonical_row = (
            db.query(GovernanceSchedule)
            .filter(
                GovernanceSchedule.job_type == alias_row.job_type,
                GovernanceSchedule.scope == canonical,
            )
            .first()
        )
        if canonical_row is None:
            alias_row.scope = canonical
            continue
        alias_ts = alias_row.last_run_at
        canonical_ts = canonical_row.last_run_at
        if alias_ts is not None and (canonical_ts is None or alias_ts > canonical_ts):
            canonical_row.last_run_at = alias_ts
        db.delete(alias_row)


def _merge_sql_references(db: Session, *, canonical: str, alias: str) -> None:
    db.query(WriteQueueJob).filter(WriteQueueJob.project == alias).update(
        {WriteQueueJob.project: canonical},
        synchronize_session=False,
    )
    db.query(WriteAuditLog).filter(WriteAuditLog.project == alias).update(
        {WriteAuditLog.project: canonical},
        synchronize_session=False,
    )
    db.query(GovernanceJob).filter(GovernanceJob.project == alias).update(
        {GovernanceJob.project: canonical},
        synchronize_session=False,
    )
    _merge_governance_schedules(db, canonical=canonical, alias=alias)

    alias_policy = (
        db.query(GovernancePolicy).filter(GovernancePolicy.project_name == alias).first()
    )
    if alias_policy is not None:
        canonical_policy = (
            db.query(GovernancePolicy)
            .filter(GovernancePolicy.project_name == canonical)
            .first()
        )
        if canonical_policy is None:
            alias_policy.project_name = canonical
        else:
            merged = {**(canonical_policy.overrides or {}), **(alias_policy.overrides or {})}
            canonical_policy.overrides = merged
            db.delete(alias_policy)

    alias_row = db.query(Project).filter(Project.name == alias).first()
    if alias_row is not None:
        db.delete(alias_row)


def apply_project_merge(
    db: Session,
    vs,
    *,
    canonical: str,
    aliases: List[str],
    job_id: str,
) -> int:
    """Move memories and SQL references from aliases into canonical."""
    canonical_row = db.query(Project).filter(Project.name == canonical).first()
    if canonical_row is None:
        upsert_project(canonical, session=db)
        canonical_row = db.query(Project).filter(Project.name == canonical).first()

    moved_total = 0
    for alias in aliases:
        if alias == canonical:
            continue
        alias_row = db.query(Project).filter(Project.name == alias).first()
        if alias_row is not None and canonical_row is not None and (
            alias_row.partition_tier != PartitionTier.shared
            or canonical_row.partition_tier != PartitionTier.shared
        ):
            logger.warning(
                "skip project merge %s -> %s: dedicated partition not supported",
                alias,
                canonical,
            )
            continue

        moved = relocate_project_memories(vs, source=alias, target=canonical)
        _merge_sql_references(db, canonical=canonical, alias=alias)
        moved_total += moved
        read_cache.invalidate_search(alias)
        read_cache.invalidate_search(canonical)
        logger.info(
            "merged project %s into %s (%s memories, job=%s)",
            alias,
            canonical,
            moved,
            job_id,
        )

    upsert_project(canonical, session=db)
    db.commit()
    return moved_total


def preview_project_merges(
    *,
    session_factory=SessionLocal,
    memory_client_provider: Optional[Callable] = None,
    llm_provider: Optional[Callable] = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> List[Dict[str, Any]]:
    if memory_client_provider is None:
        from app.utils.memory import get_memory_client_safe

        memory_client_provider = get_memory_client_safe

    client = memory_client_provider()
    if client is None:
        return []

    llm = llm_provider() if llm_provider else getattr(client, "llm", None)
    db = session_factory()
    try:
        profiles = collect_project_profiles(db)
        groups = detect_duplicate_groups_with_llm(
            profiles,
            llm,
            confidence_threshold=confidence_threshold,
        )
        return [
            {
                "canonical": g.canonical,
                "aliases": g.aliases,
                "confidence": g.confidence,
                "reason": g.reason,
                "memory_counts": {
                    name: count_project_memories(name)
                    for name in [g.canonical, *g.aliases]
                },
            }
            for g in groups
        ]
    finally:
        db.close()


def run_merge_projects_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 500,
    session_factory=SessionLocal,
    memory_client_provider: Optional[Callable] = None,
    llm_provider: Optional[Callable] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> int:
    """Detect duplicate projects with LLM and merge aliases into canonical names."""
    if memory_client_provider is None:
        from app.utils.memory import get_memory_client_safe

        memory_client_provider = get_memory_client_safe

    client = memory_client_provider()
    if client is None:
        raise RuntimeError("memory client unavailable")

    llm = llm_provider() if llm_provider else getattr(client, "llm", None)
    vs = client.vector_store

    db = session_factory()
    try:
        if payload is None:
            job = db.query(GovernanceJob).filter(GovernanceJob.id == UUID(str(job_id))).first()
            payload = dict(job.payload or {}) if job else {}
        else:
            payload = dict(payload)
        dry_run = bool(payload.get("dry_run"))
        confidence_threshold = float(
            payload.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        )
        manual_groups = payload.get("groups")

        if manual_groups:
            groups = _parse_merge_groups(
                manual_groups,
                profiles=[
                    ProjectProfile(
                        name=row.name,
                        memory_count=count_project_memories(row.name),
                        first_seen_hostname=row.first_seen_hostname,
                        samples=[],
                    )
                    for row in db.query(Project).all()
                ],
            )
        else:
            profiles = collect_project_profiles(db)
            if project:
                profiles = [p for p in profiles if p.name == project or project in p.name]
            groups = detect_duplicate_groups_with_llm(
                profiles,
                llm,
                confidence_threshold=confidence_threshold,
            )

        if dry_run:
            return len(groups)

        actions = 0
        for group in groups[: max(1, limit)]:
            canonical = _pick_canonical_by_count(group.canonical, group.aliases)
            aliases = [a for a in group.aliases if a != canonical]
            if group.canonical != canonical and group.canonical not in aliases:
                aliases.append(group.canonical)
            if not aliases:
                continue
            moved = apply_project_merge(
                db,
                vs,
                canonical=canonical,
                aliases=aliases,
                job_id=job_id,
            )
            if moved >= 0:
                actions += 1
        return actions
    finally:
        db.close()
