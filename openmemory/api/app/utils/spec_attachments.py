"""Storage de anexos de task Spec (volume dedicado — nunca Qdrant).

Bytes ficam em ``SPEC_ATTACHMENTS_DIR`` (default ``/mnt/spec-attachments``).
Metadados vivem em ``task_attachments`` (Postgres Spec SoT).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


DEFAULT_ATTACHMENTS_DIR = "/mnt/spec-attachments"


def attachments_root() -> Path:
    raw = (os.getenv("SPEC_ATTACHMENTS_DIR") or DEFAULT_ATTACHMENTS_DIR).strip()
    root = Path(raw)
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_storage_key(task_id: uuid.UUID, filename: str) -> str:
    safe = Path(filename or "file").name.replace("..", "_")
    return f"{task_id}/{uuid.uuid4().hex}_{safe}"


def absolute_path(storage_key: str) -> Path:
    root = attachments_root().resolve()
    path = (root / storage_key).resolve()
    if not str(path).startswith(str(root)):
        raise ValueError("storage_key inválido")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_bytes(storage_key: str, data: bytes) -> int:
    path = absolute_path(storage_key)
    path.write_bytes(data)
    return len(data)


def read_bytes(storage_key: str) -> bytes:
    path = absolute_path(storage_key)
    if not path.is_file():
        raise FileNotFoundError(storage_key)
    return path.read_bytes()


def delete_file(storage_key: str) -> None:
    path = absolute_path(storage_key)
    if path.is_file():
        path.unlink()
