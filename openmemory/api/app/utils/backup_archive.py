"""Camada de empacotamento de backup em .zip unificado (task_02 / ADR-003).

Reutiliza a coleta do :class:`~app.utils.backup.BackupService` (snapshot nativo do
Qdrant + ``pg_dump``) e monta um único ``.zip`` por execução, contendo::

    manifest.json
    qdrant/{collection}.snapshot
    postgres/dump.sql.gz

O ``.zip`` é gravado no diretório local da política e, quando ``mirror_s3`` está
ativo, o MESMO arquivo é espelhado no bucket S3/MinIO. A rotação FIFO mantém no
máximo ``retention`` cópias regulares; arquivos com ``tag`` (ex.: ``pre-restore``)
ficam fora da contagem. O ``restore`` (task_03) é adicionado neste mesmo módulo.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import time
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, List, Optional

from app.schemas import BackupArchiveInfo, BackupPolicySchema
from app.utils.backup import BackupService
from app.utils.metrics import (
    BACKUP_DURATION_SECONDS,
    BACKUP_ERRORS_TOTAL,
    BACKUP_LAST_SUCCESS_TIMESTAMP,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
_TS_FMT = "%Y%m%d-%H%M%S"
# Arquivo regular de backup: <timestamp>.zip (sem prefixo de tag).
_REGULAR_RE = re.compile(r"^\d{8}-\d{6}\.zip$")
_S3_ARCHIVE_PREFIX = "archives"


class ArchiveCorruptError(Exception):
    """Checksum/manifest inválidos no .zip de backup."""


class SchemaIncompatibleError(Exception):
    """``manifest.schema_version`` incompatível com esta versão do OpenMemory."""


@dataclass
class ArchiveResult:
    name: str
    path: str
    created_at: datetime
    points_count: Optional[int] = None
    mirrored_s3: bool = False
    pruned: List[str] = field(default_factory=list)


class BackupArchive:
    def __init__(
        self,
        service: BackupService,
        policy: BackupPolicySchema,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        openmemory_version: Optional[str] = None,
    ):
        self._service = service
        self._policy = policy
        self._clock = clock
        self._version = openmemory_version or os.getenv("OPENMEMORY_VERSION", "unknown")

    @property
    def policy(self) -> BackupPolicySchema:
        return self._policy

    # -- create ------------------------------------------------------------
    def create(self, *, tag: Optional[str] = None) -> ArchiveResult:
        """Coleta o estado completo, monta o ``.zip`` e aplica rotação FIFO.

        ``tag`` (ex.: ``"pre-restore"``) marca um arquivo fora da rotação FIFO.
        """
        started = time.perf_counter()
        ts = self._clock()
        name = f"{tag + '-' if tag else ''}{ts.strftime(_TS_FMT)}.zip"
        os.makedirs(self._policy.local_dir, exist_ok=True)
        final_path = os.path.join(self._policy.local_dir, name)
        tmp_path = final_path + ".tmp"
        try:
            snapshots = self._service.collect_qdrant_snapshots()
            dump = self._service.collect_pg_dump()
            points = self._service.qdrant_points_count()

            zip_bytes = self._build_zip(ts, snapshots, dump, points)
            with open(tmp_path, "wb") as fh:
                fh.write(zip_bytes)
            os.replace(tmp_path, final_path)

            result = ArchiveResult(
                name=name, path=final_path, created_at=ts, points_count=points
            )
            if self._policy.mirror_s3:
                self._mirror_to_s3(name, zip_bytes)
                result.mirrored_s3 = True
            if tag is None:
                result.pruned = self.prune()

            BACKUP_DURATION_SECONDS.set(time.perf_counter() - started)
            BACKUP_LAST_SUCCESS_TIMESTAMP.set(ts.timestamp())
            return result
        except Exception:
            BACKUP_ERRORS_TOTAL.inc()
            logger.exception("backup archive create failed")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning("could not remove temp archive %s", tmp_path)
            raise

    def _build_zip(self, ts, snapshots, dump, points) -> bytes:
        parts = []
        members = []  # (arcname, bytes)
        for col_name, data in snapshots.items():
            arc = f"qdrant/{col_name}.snapshot"
            members.append((arc, data))
            parts.append({"path": arc, "size": len(data), "sha256": _sha256(data)})
        if dump is not None:
            arc = "postgres/dump.sql.gz"
            members.append((arc, dump))
            parts.append({"path": arc, "size": len(dump), "sha256": _sha256(dump)})

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "created_at": ts.isoformat(),
            "openmemory_version": self._version,
            "collections": list(snapshots.keys()),
            "points_count": points,
            "parts": parts,
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
            for arc, data in members:
                zf.writestr(arc, data)
        return buf.getvalue()

    # -- restore (task_03 / ADR-005) --------------------------------------
    def restore(self, archive_path: str, *, safety_snapshot: bool = True) -> dict:
        """Valida o ``.zip`` e restaura o estado (PostgreSQL → Qdrant).

        Quando ``safety_snapshot`` é verdadeiro, um ``pre-restore-*.zip`` do estado
        atual é criado ANTES de sobrescrever (rede de segurança, fora da FIFO).
        Restore é sobrescrita idempotente — NÃO passa pela ``deletion_guard``.
        """
        if not os.path.exists(archive_path):
            raise FileNotFoundError(archive_path)
        members = self._read_validated_members(archive_path)

        if safety_snapshot:
            self.create(tag="pre-restore")

        restored: dict = {"postgres": None, "qdrant": []}
        dump = members.get("postgres/dump.sql.gz")
        if dump is not None:
            self._service.apply_pg_dump(dump)
            restored["postgres"] = "postgres/dump.sql.gz"
        for arc, data in members.items():
            if arc.startswith("qdrant/") and arc.endswith(".snapshot"):
                name = arc[len("qdrant/") : -len(".snapshot")]
                self._service.recover_qdrant_snapshot(name, data)
                restored["qdrant"].append(name)
        return restored

    def _read_validated_members(self, archive_path: str) -> "dict[str, bytes]":
        try:
            with zipfile.ZipFile(archive_path) as zf:
                try:
                    raw = zf.read(MANIFEST_NAME)
                except KeyError as exc:
                    raise ArchiveCorruptError("manifest.json ausente no backup") from exc
                try:
                    manifest = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ArchiveCorruptError("manifest.json inválido") from exc
                self._validate_manifest(zf, manifest)
                return {n: zf.read(n) for n in zf.namelist() if n != MANIFEST_NAME}
        except zipfile.BadZipFile as exc:
            raise ArchiveCorruptError("arquivo .zip inválido") from exc

    def _validate_manifest(self, zf: "zipfile.ZipFile", manifest: dict) -> None:
        version = manifest.get("schema_version") if isinstance(manifest, dict) else None
        if version is None:
            raise ArchiveCorruptError("manifest sem schema_version")
        if version != SCHEMA_VERSION:
            raise SchemaIncompatibleError(
                f"schema_version {version} incompatível (esperado {SCHEMA_VERSION})"
            )
        for part in manifest.get("parts", []):
            try:
                data = zf.read(part["path"])
            except KeyError as exc:
                raise ArchiveCorruptError(f"parte ausente: {part['path']}") from exc
            if _sha256(data) != part.get("sha256"):
                raise ArchiveCorruptError(f"checksum divergente em {part['path']}")

    def _mirror_to_s3(self, name: str, zip_bytes: bytes) -> None:
        s3 = self._service._s3_client()
        s3.put_object(
            Bucket=self._service._bucket,
            Key=f"{_S3_ARCHIVE_PREFIX}/{name}",
            Body=zip_bytes,
        )

    # -- list / prune ------------------------------------------------------
    def list(self) -> List[BackupArchiveInfo]:
        """Lista os ``.zip`` disponíveis (local e, se espelhado, S3)."""
        infos: List[BackupArchiveInfo] = []
        local_dir = self._policy.local_dir
        if os.path.isdir(local_dir):
            for fname in sorted(os.listdir(local_dir)):
                if not fname.endswith(".zip"):
                    continue
                path = os.path.join(local_dir, fname)
                st = os.stat(path)
                infos.append(
                    BackupArchiveInfo(
                        name=fname,
                        created_at=datetime.fromtimestamp(st.st_mtime, tz=UTC),
                        size=st.st_size,
                        points_count=_read_points_count(path),
                        location="local",
                    )
                )
        if self._policy.mirror_s3:
            infos.extend(self._list_s3())
        return infos

    def _list_s3(self) -> List[BackupArchiveInfo]:
        s3 = self._service._s3_client()
        listing = s3.list_objects_v2(
            Bucket=self._service._bucket, Prefix=_S3_ARCHIVE_PREFIX + "/"
        )
        out = []
        for obj in listing.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".zip"):
                continue
            out.append(
                BackupArchiveInfo(
                    name=key.rsplit("/", 1)[-1],
                    created_at=obj.get("LastModified"),
                    size=obj.get("Size", 0),
                    location="s3",
                )
            )
        return out

    def path_for(self, name: str) -> str:
        """Caminho local absoluto de um arquivo de backup pelo nome."""
        return os.path.join(self._policy.local_dir, os.path.basename(name))

    def has(self, name: str) -> bool:
        """Whether a local archive with ``name`` exists."""
        return os.path.exists(self.path_for(name))

    def status(self) -> dict:
        """Resumo para a UI/worker: último backup, idade (RPO), nº de cópias."""
        infos = [i for i in self.list() if i.location == "local"]
        if not infos:
            return {"last_backup": None, "rpo_age_seconds": None, "archives": 0, "last_error": None}
        newest = max(infos, key=lambda i: i.created_at or datetime.min.replace(tzinfo=UTC))
        age = None
        if newest.created_at is not None:
            age = (self._clock() - newest.created_at).total_seconds()
        return {
            "last_backup": newest.name,
            "rpo_age_seconds": age,
            "archives": len(infos),
            "last_error": None,
        }

    def prune(self) -> List[str]:
        """Remove cópias regulares além de ``retention`` (FIFO), local + S3 espelho."""
        local_dir = self._policy.local_dir
        pruned: List[str] = []
        if os.path.isdir(local_dir):
            regulars = sorted(
                f for f in os.listdir(local_dir) if _REGULAR_RE.match(f)
            )  # nome ordena cronologicamente (timestamp fixo-largura)
            excess = len(regulars) - self._policy.retention
            for fname in regulars[: max(0, excess)]:
                try:
                    os.remove(os.path.join(local_dir, fname))
                    pruned.append(fname)
                except OSError:
                    logger.warning("could not prune archive %s", fname)
        if self._policy.mirror_s3 and pruned:
            self._prune_s3(pruned)
        return pruned

    def _prune_s3(self, names: List[str]) -> None:
        s3 = self._service._s3_client()
        for name in names:
            try:
                s3.delete_object(
                    Bucket=self._service._bucket, Key=f"{_S3_ARCHIVE_PREFIX}/{name}"
                )
            except Exception:  # noqa: BLE001 — espelho é best-effort
                logger.warning("could not prune S3 mirror %s", name)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_points_count(zip_path: str) -> Optional[int]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read(MANIFEST_NAME))
        return manifest.get("points_count")
    except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return None
