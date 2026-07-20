from typing import Optional, Set
from uuid import UUID

from app.models import AccessControl, App, Memory, MemoryState
from sqlalchemy.orm import Session


def check_memory_access_permissions(
    db: Session,
    memory: Memory,
    app_id: Optional[UUID] = None
) -> bool:
    """
    Check if the given app has permission to access a memory based on:
    1. Memory state (must be active)
    2. App state (must not be paused)
    3. App-specific access controls

    Args:
        db: Database session
        memory: Memory object to check access for
        app_id: Optional app ID to check permissions for

    Returns:
        bool: True if access is allowed, False otherwise
    """
    # Check if memory is active
    if memory.state != MemoryState.active:
        return False

    # If no app_id provided, only check memory state
    if not app_id:
        return True

    # Check if app exists and is active
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        return False

    # Check if app is paused/inactive
    if not app.is_active:
        return False

    # Check app-specific access controls
    from app.routers.memories import get_accessible_memory_ids
    accessible_memory_ids = get_accessible_memory_ids(db, app_id)

    # If accessible_memory_ids is None, all memories are accessible
    if accessible_memory_ids is None:
        return True

    # Check if memory is in the accessible set
    return memory.id in accessible_memory_ids


def get_accessible_spec_workspace_ids(
    db: Session,
    subject_type: str,
    subject_id: Optional[UUID],
) -> Optional[Set[UUID]]:
    """Conjunto de ``SpecWorkspace`` acessíveis por um sujeito (ADR-004).

    Reaproveita o mesmo padrão de resolução allow/deny de
    ``get_accessible_memory_ids``, agora sobre ``object_type="spec_workspace"``:

    - Sem nenhuma regra para o sujeito -> ``None`` (todos os workspaces são
      acessíveis, comportamento aberto por padrão como nas memórias).
    - Regra ``allow`` sem ``object_id`` -> ``None`` (acesso a todos).
    - Regra ``deny`` sem ``object_id`` -> ``set()`` (nenhum acessível).
    - Caso contrário, retorna o conjunto de ``allow`` menos os ``deny``.
    """
    rules = (
        db.query(AccessControl)
        .filter(
            AccessControl.subject_type == subject_type,
            AccessControl.subject_id == subject_id,
            AccessControl.object_type == "spec_workspace",
        )
        .all()
    )

    if not rules:
        return None

    allowed_ids: Set[UUID] = set()
    denied_ids: Set[UUID] = set()
    for rule in rules:
        if rule.effect == "allow":
            if rule.object_id:
                allowed_ids.add(rule.object_id)
            else:
                return None
        elif rule.effect == "deny":
            if rule.object_id:
                denied_ids.add(rule.object_id)
            else:
                return set()

    if allowed_ids:
        allowed_ids -= denied_ids
    return allowed_ids
