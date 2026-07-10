"""Per-user and per-group analytics from write/read audit tables."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from app.models import User, WriteAuditLog, WriteQueueJob, USER_TYPE_LEGACY_HOST, get_current_utc_time
from app.read_audit_log_model import ReadAuditLog
from app.utils.machine_resolver import legacy_hostname_variants
from app.utils.read_audit import read_audit_hostname_variants
from sqlalchemy import case, func
from sqlalchemy.orm import Session

UsageLevel = str  # online | offline

PREVIEW_MAX_LEN = 160


def _truncate_preview(text: Optional[str], *, limit: int = PREVIEW_MAX_LEN) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


def _since(hours: Optional[int] = None, days: Optional[int] = None) -> Optional[datetime]:
    if hours is None and days is None:
        return None
    now = get_current_utc_time()
    if hours is not None:
        return now - timedelta(hours=hours)
    return now - timedelta(days=days)


def _audit_variants_for_hosts(db: Session, hostnames: list[str]) -> tuple[list[str], dict[str, str]]:
    """Expande hostnames para variantes de auditoria e mapeia de volta ao membro canônico."""
    all_variants: list[str] = []
    variant_to_member: dict[str, str] = {}
    for host in hostnames:
        keys = set(legacy_hostname_variants(db, host))
        for variant in read_audit_hostname_variants(host):
            keys.add(variant)
        for variant in keys:
            all_variants.append(variant)
            variant_to_member[variant] = host
    return all_variants, variant_to_member


def _write_stats_for_hostnames(
    db: Session,
    hostnames: list[str],
    *,
    since: Optional[datetime] = None,
) -> dict[str, dict]:
    if not hostnames:
        return {}
    all_variants, variant_to_member = _audit_variants_for_hosts(db, hostnames)
    if not all_variants:
        return {}
    q = db.query(
        WriteAuditLog.hostname,
        func.count(WriteAuditLog.id).label("total"),
        func.count(func.distinct(WriteAuditLog.project)).label("projects"),
        func.max(WriteAuditLog.created_at).label("last_at"),
    ).filter(WriteAuditLog.hostname.in_(all_variants))
    if since is not None:
        q = q.filter(WriteAuditLog.created_at >= since)
    rows = q.group_by(WriteAuditLog.hostname).all()

    result: dict[str, dict] = {
        host: {"total": 0, "projects": 0, "last_at": None} for host in hostnames
    }
    project_sets: dict[str, set[str]] = {host: set() for host in hostnames}
    for row in rows:
        member = variant_to_member.get(row.hostname, row.hostname)
        if member not in result:
            continue
        bucket = result[member]
        bucket["total"] += int(row.total or 0)
        if row.last_at and (bucket["last_at"] is None or row.last_at > bucket["last_at"]):
            bucket["last_at"] = row.last_at

    project_rows = (
        db.query(WriteAuditLog.hostname, WriteAuditLog.project)
        .filter(WriteAuditLog.hostname.in_(all_variants))
        .distinct()
    )
    if since is not None:
        project_rows = project_rows.filter(WriteAuditLog.created_at >= since)
    for hostname, project in project_rows:
        member = variant_to_member.get(hostname, hostname)
        if member in project_sets and project:
            project_sets[member].add(project)

    for host in hostnames:
        result[host]["projects"] = len(project_sets[host])
    return result


def _read_stats_for_hostnames(
    db: Session,
    hostnames: list[str],
    *,
    since: Optional[datetime] = None,
) -> dict[str, dict]:
    if not hostnames:
        return {}

    all_variants, variant_to_member = _audit_variants_for_hosts(db, hostnames)
    if not all_variants:
        return {}

    canonical = case(
        (ReadAuditLog.hostname.like("ui:%"), func.substr(ReadAuditLog.hostname, 4)),
        else_=ReadAuditLog.hostname,
    )

    q = db.query(
        canonical.label("canonical"),
        func.count(ReadAuditLog.id).label("total"),
        func.count(func.distinct(ReadAuditLog.project)).label("projects"),
        func.count(func.distinct(ReadAuditLog.memory_id)).label("memories"),
        func.max(ReadAuditLog.accessed_at).label("last_at"),
    ).filter(ReadAuditLog.hostname.in_(all_variants))
    if since is not None:
        q = q.filter(ReadAuditLog.accessed_at >= since)
    rows = q.group_by(canonical).all()

    result: dict[str, dict] = {
        host: {"total": 0, "projects": 0, "memories": 0, "last_at": None} for host in hostnames
    }
    for row in rows:
        key = (row.canonical or "").strip()
        member = variant_to_member.get(key, key)
        if member not in result:
            continue
        bucket = result[member]
        bucket["total"] += int(row.total or 0)
        bucket["projects"] += int(row.projects or 0)
        bucket["memories"] += int(row.memories or 0)
        if row.last_at and (bucket["last_at"] is None or row.last_at > bucket["last_at"]):
            bucket["last_at"] = row.last_at
    return result


def _last_interaction_at(
    last_write_at: Optional[datetime],
    last_read_at: Optional[datetime],
) -> Optional[datetime]:
    candidates = [dt for dt in (last_write_at, last_read_at) if dt is not None]
    if not candidates:
        return None
    return max(candidates)


def classify_presence(
    *,
    writes_24h: int,
    reads_24h: int,
    last_write_at: Optional[datetime],
    last_read_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> tuple[UsageLevel, Optional[int]]:
    """Online = escrita ou leitura nas últimas 24h; offline = sem interação nesse período."""
    if writes_24h > 0 or reads_24h > 0:
        return "online", None

    last_at = _last_interaction_at(last_write_at, last_read_at)
    if last_at is None:
        return "offline", None

    reference = now or get_current_utc_time()
    elapsed = reference - last_at
    offline_days = max(1, elapsed.days)
    return "offline", offline_days


def user_activity_stats(db: Session, hostname: str) -> dict:
    """Aggregate write/read counts for a single hostname."""
    writes_all = _write_stats_for_hostnames(db, [hostname])
    reads_all = _read_stats_for_hostnames(db, [hostname])
    writes_24h = _write_stats_for_hostnames(db, [hostname], since=_since(hours=24))
    reads_24h = _read_stats_for_hostnames(db, [hostname], since=_since(hours=24))
    writes_7d = _write_stats_for_hostnames(db, [hostname], since=_since(days=7))
    reads_7d = _read_stats_for_hostnames(db, [hostname], since=_since(days=7))
    writes_30d = _write_stats_for_hostnames(db, [hostname], since=_since(days=30))
    reads_30d = _read_stats_for_hostnames(db, [hostname], since=_since(days=30))

    w = writes_all.get(hostname, {})
    r = reads_all.get(hostname, {})
    w24 = writes_24h.get(hostname, {})
    r24 = reads_24h.get(hostname, {})
    w7 = writes_7d.get(hostname, {})
    r7 = reads_7d.get(hostname, {})
    w30 = writes_30d.get(hostname, {})
    r30 = reads_30d.get(hostname, {})

    writes_total = w.get("total", 0)
    reads_total = r.get("total", 0)
    writes_7d_count = w7.get("total", 0)
    reads_7d_count = r7.get("total", 0)
    writes_30d_count = w30.get("total", 0)
    reads_30d_count = r30.get("total", 0)
    last_write_at = w.get("last_at")
    last_read_at = r.get("last_at")
    usage_level, offline_days = classify_presence(
        writes_24h=w24.get("total", 0),
        reads_24h=r24.get("total", 0),
        last_write_at=last_write_at,
        last_read_at=last_read_at,
    )

    return {
        "writes_total": writes_total,
        "writes_24h": w24.get("total", 0),
        "writes_7d": writes_7d_count,
        "writes_30d": writes_30d_count,
        "reads_total": reads_total,
        "reads_24h": r24.get("total", 0),
        "reads_7d": reads_7d_count,
        "reads_30d": reads_30d_count,
        "distinct_projects_written": w.get("projects", 0),
        "distinct_projects_read": r.get("projects", 0),
        "distinct_memories_read": r.get("memories", 0),
        "last_write_at": last_write_at,
        "last_read_at": last_read_at,
        "usage_level": usage_level,
        "offline_days": offline_days,
    }


def group_activity_stats(db: Session, group_id: UUID) -> dict:
    """Roll up write/read stats across all members of a group."""
    members = (
        db.query(User.user_id)
        .filter(User.group_id == group_id, User.user_type == USER_TYPE_LEGACY_HOST)
        .all()
    )
    hostnames = [m.user_id for m in members]
    if not hostnames:
        return {
            "member_count": 0,
            "active_members_7d": 0,
            "writes_total": 0,
            "writes_24h": 0,
            "writes_7d": 0,
            "reads_total": 0,
            "reads_24h": 0,
            "reads_7d": 0,
        }

    writes_all = _write_stats_for_hostnames(db, hostnames)
    reads_all = _read_stats_for_hostnames(db, hostnames)
    writes_24h = _write_stats_for_hostnames(db, hostnames, since=_since(hours=24))
    reads_24h = _read_stats_for_hostnames(db, hostnames, since=_since(hours=24))
    writes_7d = _write_stats_for_hostnames(db, hostnames, since=_since(days=7))
    reads_7d = _read_stats_for_hostnames(db, hostnames, since=_since(days=7))

    writes_total = sum(v.get("total", 0) for v in writes_all.values())
    reads_total = sum(v.get("total", 0) for v in reads_all.values())
    writes_24h_total = sum(v.get("total", 0) for v in writes_24h.values())
    reads_24h_total = sum(v.get("total", 0) for v in reads_24h.values())
    writes_7d_total = sum(v.get("total", 0) for v in writes_7d.values())
    reads_7d_total = sum(v.get("total", 0) for v in reads_7d.values())

    active_7d = 0
    for host in hostnames:
        w7 = writes_7d.get(host, {}).get("total", 0)
        r7 = reads_7d.get(host, {}).get("total", 0)
        if w7 > 0 or r7 > 0:
            active_7d += 1

    return {
        "member_count": len(hostnames),
        "active_members_7d": active_7d,
        "writes_total": writes_total,
        "writes_24h": writes_24h_total,
        "writes_7d": writes_7d_total,
        "reads_total": reads_total,
        "reads_24h": reads_24h_total,
        "reads_7d": reads_7d_total,
    }


def recent_user_writes(db: Session, hostname: str, *, limit: int = 20) -> list[dict]:
    variants = legacy_hostname_variants(db, hostname)
    rows = (
        db.query(WriteAuditLog, WriteQueueJob)
        .outerjoin(WriteQueueJob, WriteAuditLog.job_id == WriteQueueJob.id)
        .filter(WriteAuditLog.hostname.in_(variants))
        .order_by(WriteAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(audit.id),
            "job_id": str(audit.job_id) if audit.job_id else None,
            "project": audit.project,
            "client_name": audit.client_name,
            "action": audit.action,
            "created_at": audit.created_at,
            "text": job.text if job else None,
            "text_preview": _truncate_preview(job.text if job else None),
        }
        for audit, job in rows
    ]


def recent_user_reads(db: Session, hostname: str, *, limit: int = 20) -> list[dict]:
    from app.utils.vector_stats import get_shared_memories_by_ids

    variants: list[str] = []
    for host_variant in legacy_hostname_variants(db, hostname):
        variants.extend(read_audit_hostname_variants(host_variant))
    if not variants:
        return []
    rows = (
        db.query(ReadAuditLog)
        .filter(ReadAuditLog.hostname.in_(variants))
        .order_by(ReadAuditLog.accessed_at.desc())
        .limit(limit)
        .all()
    )
    memory_ids = [str(row.memory_id) for row in rows if row.memory_id]
    memories = get_shared_memories_by_ids(memory_ids)

    items: list[dict] = []
    for row in rows:
        memory = memories.get(str(row.memory_id)) or {}
        text = memory.get("text") or ""
        items.append(
            {
                "id": str(row.id),
                "project": row.project,
                "memory_id": row.memory_id,
                "access_type": row.access_type,
                "source": row.source,
                "client_name": row.client_name,
                "accessed_at": row.accessed_at,
                "memory_preview": _truncate_preview(text),
                "memory_text": text or None,
            }
        )
    return items
