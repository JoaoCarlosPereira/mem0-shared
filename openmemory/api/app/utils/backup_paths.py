"""Mapeamento entre o caminho de backup no host e o mount no container.

``docker-compose.scale.yml`` monta ``LOCAL_BACKUP_DIR`` (host) em ``/mnt/backups``
(container). A política e a UI usam o caminho do **host**; operações de I/O usam
o caminho **resolvido** dentro do container.
"""

from __future__ import annotations

import os

from app.schemas import BackupPolicySchema

CONTAINER_BACKUP_MOUNT = "/mnt/backups"


def host_backup_dir() -> str | None:
    """Caminho no host definido por ``LOCAL_BACKUP_DIR`` (compose / .env)."""
    raw = (os.getenv("LOCAL_BACKUP_DIR") or "").strip()
    return raw or None


def default_local_dir() -> str:
    """Valor padrão da política — host quando configurado, senão mount do container."""
    return host_backup_dir() or CONTAINER_BACKUP_MOUNT


def _norm(path: str) -> str:
    return os.path.normpath(path.rstrip("/") or "/")


def to_container_path(path: str) -> str:
    """Traduz caminho do host (ou legado) para o mount usado em runtime."""
    host = host_backup_dir()
    if host and _norm(path) == _norm(host):
        return CONTAINER_BACKUP_MOUNT
    return path


def to_host_path(path: str) -> str:
    """Expõe o caminho do host na API/UI quando há mount configurado."""
    host = host_backup_dir()
    if host and _norm(path) == _norm(CONTAINER_BACKUP_MOUNT):
        return host
    return path


def externalize_policy(policy: BackupPolicySchema) -> BackupPolicySchema:
    """Política para resposta da API (caminho legível no host)."""
    return policy.model_copy(update={"local_dir": to_host_path(policy.local_dir)})


def internalize_policy(policy: BackupPolicySchema) -> BackupPolicySchema:
    """Política para I/O no filesystem do container."""
    return policy.model_copy(update={"local_dir": to_container_path(policy.local_dir)})


def policy_for_storage(policy: BackupPolicySchema) -> BackupPolicySchema:
    """Normaliza ``local_dir`` antes de persistir (prefere caminho do host)."""
    return policy.model_copy(
        update={"local_dir": to_host_path(to_container_path(policy.local_dir))}
    )
