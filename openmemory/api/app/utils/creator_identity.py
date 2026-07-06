"""Resolve linked person display info for machine hostnames (ADR-005).

Write paths store ``hostname`` on memories and queue jobs. Read paths enrich
responses with the Google-linked person's ``display_name`` and ``avatar_url``
when the machine is in ``linked`` status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.utils.identity import resolve_hostname


@dataclass(frozen=True)
class CreatorIdentity:
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


def _normalize_hostnames(hostnames: Iterable[Optional[str]]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for raw in hostnames:
        if not raw:
            continue
        key = resolve_hostname(str(raw))
        if not key or key == "unknown-host" or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def resolve_creator_identities_with_db(
    db: Session,
    hostnames: Iterable[Optional[str]],
) -> dict[str, CreatorIdentity]:
    """Batch-resolve hostnames using an existing SQLAlchemy session."""
    keys = _normalize_hostnames(hostnames)
    if not keys:
        return {}

    from app.models import Machine, MachineStatus, User

    try:
        rows = (
            db.query(Machine.hostname, User.display_name, User.avatar_url, User.name)
            .join(User, Machine.linked_user_id == User.id)
            .filter(
                Machine.hostname.in_(keys),
                Machine.status == MachineStatus.linked,
                Machine.linked_user_id.isnot(None),
            )
            .all()
        )
        return {
            hostname: CreatorIdentity(
                display_name=display_name or name,
                avatar_url=avatar_url,
            )
            for hostname, display_name, avatar_url, name in rows
        }
    except Exception:  # noqa: BLE001 - enrichment is best-effort on read paths
        return {}


def resolve_creator_identities(
    hostnames: Iterable[Optional[str]],
) -> dict[str, CreatorIdentity]:
    """Batch-resolve hostnames to linked person display fields.

    Returns a map keyed by normalized hostname. Missing or unlinked hostnames
    are omitted (best-effort; never raises).
    """
    keys = _normalize_hostnames(hostnames)
    if not keys:
        return {}

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return resolve_creator_identities_with_db(db, keys)
    except Exception:  # noqa: BLE001 - enrichment is best-effort on read paths
        return {}
    finally:
        db.close()


def identity_for_hostname(
    hostname: Optional[str],
    identities: dict[str, CreatorIdentity],
) -> Optional[CreatorIdentity]:
    if not hostname:
        return None
    return identities.get(resolve_hostname(str(hostname)))


def enrich_memory_attribution(
    item: dict[str, Any],
    identities: dict[str, CreatorIdentity],
    *,
    hostname_key: str = "created_by_hostname",
) -> None:
    """Attach ``created_by_display_name`` / ``created_by_avatar_url`` in-place."""
    identity = identity_for_hostname(item.get(hostname_key), identities)
    if identity is None:
        return
    if identity.display_name:
        item["created_by_display_name"] = identity.display_name
    if identity.avatar_url:
        item["created_by_avatar_url"] = identity.avatar_url


def enrich_memory_items(
    items: list[dict[str, Any]],
    *,
    hostname_key: str = "created_by_hostname",
) -> None:
    """Resolve and attach creator identity fields for a list of memory dicts."""
    identities = resolve_creator_identities(item.get(hostname_key) for item in items)
    for item in items:
        enrich_memory_attribution(item, identities, hostname_key=hostname_key)


def enrich_actor_fields(
    item: dict[str, Any],
    identities: dict[str, CreatorIdentity],
    *,
    hostname_key: str = "hostname",
    display_name_key: str = "display_name",
    avatar_url_key: str = "avatar_url",
) -> None:
    """Attach person display fields for queue/audit/access-log rows."""
    identity = identity_for_hostname(item.get(hostname_key), identities)
    if identity is None:
        return
    if identity.display_name:
        item[display_name_key] = identity.display_name
    if identity.avatar_url:
        item[avatar_url_key] = identity.avatar_url


def enrich_actor_items(
    items: list[dict[str, Any]],
    *,
    hostname_key: str = "hostname",
    display_name_key: str = "display_name",
    avatar_url_key: str = "avatar_url",
) -> None:
    identities = resolve_creator_identities(item.get(hostname_key) for item in items)
    for item in items:
        enrich_actor_fields(
            item,
            identities,
            hostname_key=hostname_key,
            display_name_key=display_name_key,
            avatar_url_key=avatar_url_key,
        )
