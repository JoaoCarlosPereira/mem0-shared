"""Arquivos de anexos Spec + PLANKA no backup unificado (tar.gz).

Volumes dedicados — nunca Qdrant. Incluídos no ``.zip`` do ``BackupArchive``
como ``attachments/spec.tar.gz`` e ``attachments/planka.tar.gz``.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import tarfile
from pathlib import Path
from typing import Dict, Mapping, Optional

logger = logging.getLogger(__name__)

DEFAULT_SPEC_DIR = "/mnt/spec-attachments"
DEFAULT_PLANKA_DIR = "/mnt/planka-attachments"

SPEC_ARCNAME = "attachments/spec.tar.gz"
PLANKA_ARCNAME = "attachments/planka.tar.gz"


def attachment_roots(
    *,
    spec_dir: Optional[str] = None,
    planka_dir: Optional[str] = None,
) -> Dict[str, Path]:
    """Mapa arcname → raiz do volume."""
    spec = (
        spec_dir
        if spec_dir is not None
        else (os.getenv("SPEC_ATTACHMENTS_DIR") or DEFAULT_SPEC_DIR)
    ).strip()
    planka = (
        planka_dir
        if planka_dir is not None
        else (os.getenv("PLANKA_ATTACHMENTS_DIR") or DEFAULT_PLANKA_DIR)
    ).strip()
    return {
        SPEC_ARCNAME: Path(spec),
        PLANKA_ARCNAME: Path(planka),
    }


def _empty_tar_gz() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz"):
        pass
    return buf.getvalue()


def _tar_gz_directory(root: Path) -> bytes:
    """Empacota o conteúdo de ``root`` (relativo à raiz). Ausente/vazio → tar vazio."""
    if not root.is_dir():
        return _empty_tar_gz()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            tf.add(child, arcname=child.name, recursive=True)
    return buf.getvalue()


def _clear_directory(root: Path) -> None:
    """Remove conteúdo de ``root`` sem apagar o mount point."""
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def _safe_extract(tf: tarfile.TarFile, dest: Path) -> None:
    """Extrai tar impedindo path traversal."""
    dest_resolved = dest.resolve()
    for member in tf.getmembers():
        name = member.name
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError(f"membro de tar inseguro: {name}")
        target = (dest / name).resolve()
        if not str(target).startswith(str(dest_resolved)):
            raise ValueError(f"membro de tar fora do destino: {name}")
    # filter="data" (3.12+) bloqueia links absolutos; fallback para extractall clássico.
    try:
        tf.extractall(path=dest, filter=tarfile.data_filter)  # type: ignore[arg-type]
    except (AttributeError, TypeError):
        tf.extractall(path=dest)


def collect_attachment_archives(
    *,
    roots: Optional[Mapping[str, Path]] = None,
) -> Dict[str, bytes]:
    """``{arcname: tar.gz bytes}`` para Spec e PLANKA (sempre ambos)."""
    mapping = dict(roots) if roots is not None else attachment_roots()
    out: Dict[str, bytes] = {}
    for arcname, root in mapping.items():
        try:
            out[arcname] = _tar_gz_directory(root)
        except OSError:
            logger.warning("could not archive attachments at %s", root, exc_info=True)
            out[arcname] = _empty_tar_gz()
    return out


def apply_attachment_archive(
    arcname: str,
    data: bytes,
    *,
    roots: Optional[Mapping[str, Path]] = None,
) -> str:
    """Limpa a raiz correspondente e extrai o ``tar.gz``. Retorna o arcname aplicado."""
    mapping = dict(roots) if roots is not None else attachment_roots()
    if arcname not in mapping:
        raise KeyError(f"arcname de anexos desconhecido: {arcname}")
    root = mapping[arcname]
    root.mkdir(parents=True, exist_ok=True)
    _clear_directory(root)
    buf = io.BytesIO(data)
    with tarfile.open(fileobj=buf, mode="r:gz") as tf:
        _safe_extract(tf, root)
    return arcname
