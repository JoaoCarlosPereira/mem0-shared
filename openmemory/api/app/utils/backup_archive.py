"""Camada de empacotamento de backup em .zip unificado (task_02 / ADR-003).

Reutiliza a coleta do :class:`~app.utils.backup.BackupService` (snapshot nativo do
Qdrant + ``pg_dump`` + anexos Spec/PLANKA) e monta um único ``.zip`` por execução,
contendo::

    manifest.json
    qdrant/{collection}.snapshot
    postgres/dump.sql.gz
    attachments/spec.tar.gz
    attachments/planka.tar.gz

O ``.zip`` é gravado no diretório local da política e, quando ``mirror_s3`` está
ativo, o MESMO arquivo é espelhado no bucket S3/MinIO. A rotação FIFO mantém no
máximo ``retention`` cópias regulares; arquivos com ``tag`` (ex.: ``pre-restore``)
ficam fora da contagem. O ``restore`` (task_03) é adicionado neste mesmo módulo.
"""

from __future__ import annotations

import hashlib
import gzip
import io
import json
import logging
import os
import re
import tarfile
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

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, SCHEMA_VERSION}
MANIFEST_NAME = "manifest.json"
_LAST_ERROR_NAME = ".last_error"
_VERIFICATION_SUFFIX = ".verification.json"
_TS_FMT = "%Y%m%d-%H%M%S"
# Arquivo regular de backup: <timestamp>.zip (sem prefixo de tag).
_REGULAR_RE = re.compile(r"^\d{8}-\d{6}\.zip$")
_S3_ARCHIVE_PREFIX = "archives"


# -- progresso (reportado em /admin/backup/status) ------------------------- #
class BackupProgressTracker:
    """Estado em memória de uma operação de backup/restore (worker único).

    A tarefa roda em background (FastAPI ``BackgroundTasks``) e o endpoint de
    status lê o MESMO objeto no MESMO processo. Sem lock por ser single-worker:
    as atribuições são visíveis para o polling da UI e o pior caso é ler um
    percent ligeiramente atrasado.
    """

    def __init__(self) -> None:
        self.operation: Optional[str] = None
        self.phase: Optional[str] = None
        self.percent: int = 0
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.ok: Optional[bool] = None
        self.error: Optional[str] = None

    def start(self, operation: str) -> None:
        self.operation = operation
        self.phase = None
        self.percent = 0
        self.started_at = datetime.now(UTC)
        self.finished_at = None
        self.ok = None
        self.error = None

    def advance(self, phase: str, percent: int) -> None:
        self.phase = phase
        self.percent = max(0, min(100, int(percent)))

    def finish(self, ok: bool, error: Optional[str] = None) -> None:
        self.finished_at = datetime.now(UTC)
        self.ok = ok
        self.error = error
        if ok:
            self.percent = 100

    def to_dict(self) -> Optional[dict]:
        if self.operation is None:
            return None
        return {
            "operation": self.operation,
            "phase": self.phase,
            "percent": self.percent,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "ok": self.ok,
            "error": self.error,
        }


_PROGRESS = BackupProgressTracker()


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
    verification_status: str = "unverified"


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
    def create(
        self,
        *,
        tag: Optional[str] = None,
        report: Optional[bool] = None,
    ) -> ArchiveResult:
        """Coleta o estado completo, monta o ``.zip`` e aplica rotação FIFO.

        ``tag`` (ex.: ``"pre-restore"``) marca um arquivo fora da rotação FIFO.
        ``report`` controla o progresso reportado em /status (default: só backup
        manual, tag=None) — o snapshot de segurança de um restore não deve
        sobrepor a barra de restore.
        """
        started = time.perf_counter()
        ts = self._clock()
        name = f"{tag + '-' if tag else ''}{ts.strftime(_TS_FMT)}.zip"
        os.makedirs(self._policy.local_dir, exist_ok=True)
        final_path = os.path.join(self._policy.local_dir, name)
        tmp_path = final_path + ".tmp"
        report = (tag is None) if report is None else report
        if report:
            _PROGRESS.start("backup")
        try:
            if report:
                _PROGRESS.advance("snapshot do Qdrant", 15)
            snapshots = self._service.collect_qdrant_snapshots()
            if report:
                _PROGRESS.advance("dump do PostgreSQL", 50)
            dump = self._service.collect_pg_dump()
            if report:
                _PROGRESS.advance("coleta de anexos", 80)
            attachments = self._service.collect_attachment_archives()
            collection_points = self._service.qdrant_collection_points()
            points = sum(collection_points.values()) if collection_points else None

            if report:
                _PROGRESS.advance("arquivando .zip", 92)
            zip_bytes = self._build_zip(
                ts,
                snapshots,
                dump,
                points,
                attachments,
                collection_points=collection_points,
            )
            with open(tmp_path, "wb") as fh:
                fh.write(zip_bytes)
            os.replace(tmp_path, final_path)

            verification = self.verify_archive(final_path)
            result = ArchiveResult(
                name=name,
                path=final_path,
                created_at=ts,
                points_count=points,
                verification_status=verification["status"],
            )
            if self._policy.mirror_s3:
                self._mirror_to_s3(name, zip_bytes)
                result.mirrored_s3 = True
            if tag is None:
                result.pruned = self.prune()

            self._clear_last_error()
            BACKUP_DURATION_SECONDS.set(time.perf_counter() - started)
            BACKUP_LAST_SUCCESS_TIMESTAMP.set(ts.timestamp())
            if report:
                _PROGRESS.finish(True)
            return result
        except Exception as exc:
            BACKUP_ERRORS_TOTAL.inc()
            logger.exception("backup archive create failed")
            self._write_last_error(str(exc) or exc.__class__.__name__)
            if report:
                _PROGRESS.finish(False, str(exc) or exc.__class__.__name__)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    logger.warning("could not remove temp archive %s", tmp_path)
            raise

    def _build_zip(
        self,
        ts,
        snapshots,
        dump,
        points,
        attachments=None,
        *,
        collection_points=None,
    ) -> bytes:
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
        for arc, data in (attachments or {}).items():
            members.append((arc, data))
            parts.append({"path": arc, "size": len(data), "sha256": _sha256(data)})

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "backup_format": SCHEMA_VERSION,
            "restore_engine_version": SCHEMA_VERSION,
            "created_at": ts.isoformat(),
            "openmemory_version": self._version,
            "collections": list(snapshots.keys()),
            "points_count": points,
            "qdrant": {
                "collections": {
                    name: {
                        "points_count": (collection_points or {}).get(name),
                        "snapshot": f"qdrant/{name}.snapshot",
                    }
                    for name in snapshots
                }
            },
            "postgres": {
                "dump_format": "plain-sql-gzip",
                "present": dump is not None,
                "schemas": ["public", "planka", "agentregistry"],
            },
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
        """Valida o ``.zip`` e restaura o estado (PostgreSQL → Qdrant → anexos).

        Quando ``safety_snapshot`` é verdadeiro, um ``pre-restore-*.zip`` do estado
        atual é criado ANTES de sobrescrever (rede de segurança, fora da FIFO).
        Restore é sobrescrita idempotente — NÃO passa pela ``deletion_guard``.
        Zips legados sem ``attachments/*.tar.gz`` restauram só PG + Qdrant.
        """
        if not os.path.exists(archive_path):
            raise FileNotFoundError(archive_path)
        _PROGRESS.start("restore")
        try:
            _PROGRESS.advance("lendo backup", 5)
            manifest, members = self._read_validated_archive(archive_path)
            self.assert_restore_allowed(archive_path)

            _PROGRESS.advance("snapshot de segurança", 10)
            safety_archive = None
            if safety_snapshot:
                # report=False: não sobrepõe a barra de restore na UI.
                safety_archive = self.create(tag="pre-restore", report=False)
                # O ponto de reversão só é válido depois de reabrir o arquivo e
                # verificar novamente manifest + checksums gravados em disco.
                self._read_validated_members(safety_archive.path)

            _PROGRESS.advance("restaurando PostgreSQL", 30)
            restored: dict = {
                "postgres": None,
                "qdrant": [],
                "attachments": [],
                "pre_restore": safety_archive.name if safety_archive else None,
            }
            dump = members.get("postgres/dump.sql.gz")
            if dump is not None:
                self._service.apply_pg_dump(dump)
                restored["postgres"] = "postgres/dump.sql.gz"

            _PROGRESS.advance("restaurando Qdrant", 70)
            for arc, data in members.items():
                if arc.startswith("qdrant/") and arc.endswith(".snapshot"):
                    name = arc[len("qdrant/") : -len(".snapshot")]
                    self._service.recover_qdrant_snapshot(name, data)
                    restored["qdrant"].append(name)

            _PROGRESS.advance("restaurando anexos", 90)
            for arc, data in members.items():
                if arc.startswith("attachments/") and arc.endswith(".tar.gz"):
                    self._service.apply_attachment_archive(arc, data)
                    restored["attachments"].append(arc)

            _PROGRESS.advance("verificando estado restaurado", 96)
            self._verify_restored_qdrant(manifest)

            _PROGRESS.finish(True)
            return restored
        except Exception as exc:
            _PROGRESS.finish(False, str(exc) or exc.__class__.__name__)
            raise

    def _read_validated_members(self, archive_path: str) -> "dict[str, bytes]":
        return self._read_validated_archive(archive_path)[1]

    def _read_validated_archive(self, archive_path: str) -> "tuple[dict, dict[str, bytes]]":
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
                members = {n: zf.read(n) for n in zf.namelist() if n != MANIFEST_NAME}
                return manifest, members
        except zipfile.BadZipFile as exc:
            raise ArchiveCorruptError("arquivo .zip inválido") from exc

    def _validate_manifest(self, zf: "zipfile.ZipFile", manifest: dict) -> None:
        version = manifest.get("schema_version") if isinstance(manifest, dict) else None
        if version is None:
            raise ArchiveCorruptError("manifest sem schema_version")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise SchemaIncompatibleError(
                f"schema_version {version} incompatível "
                f"(suportados: {sorted(SUPPORTED_SCHEMA_VERSIONS)})"
            )
        for part in manifest.get("parts", []):
            try:
                data = zf.read(part["path"])
            except KeyError as exc:
                raise ArchiveCorruptError(f"parte ausente: {part['path']}") from exc
            if _sha256(data) != part.get("sha256"):
                raise ArchiveCorruptError(f"checksum divergente em {part['path']}")

    def verification_path(self, archive_path: str) -> str:
        return archive_path + _VERIFICATION_SUFFIX

    def verify_archive(self, archive_path: str) -> dict:
        """Certifica estrutura, checksums e contrato do ZIP pelo seu SHA-256."""
        report = {
            "backup_sha256": None,
            "restore_engine_version": SCHEMA_VERSION,
            "verified_at": self._clock().isoformat(),
            "status": "invalid",
            "error": None,
        }
        try:
            manifest, members = self._read_validated_archive(archive_path)
            digest = _sha256_file(archive_path)
            report["backup_sha256"] = digest
            version = int(manifest["schema_version"])
            self._validate_required_content(manifest, members, version)
            if version == SCHEMA_VERSION:
                report["status"] = "verified"
            else:
                report["status"] = "legacy_verified"
        except SchemaIncompatibleError as exc:
            report["status"] = "incompatible"
            report["error"] = str(exc)
        except Exception as exc:
            report["status"] = "invalid"
            report["error"] = str(exc) or exc.__class__.__name__
        self._write_verification(archive_path, report)
        return report

    def verification(self, archive_path: str) -> dict:
        """Retorna certificação válida para o conteúdo atual ou recertifica."""
        expected_digest = _sha256_file(archive_path)
        path = self.verification_path(archive_path)
        try:
            with open(path, encoding="utf-8") as fh:
                report = json.load(fh)
            if report.get("backup_sha256") == expected_digest:
                return report
        except (OSError, json.JSONDecodeError):
            pass
        return self.verify_archive(archive_path)

    def inspection(self, archive_path: str, *, persist: bool = True) -> dict:
        """Inspeciona restaurabilidade; persistência é opcional para mídias read-only."""
        if persist:
            return self.verification(archive_path)
        try:
            manifest, members = self._read_validated_archive(archive_path)
            version = int(manifest["schema_version"])
            self._validate_required_content(manifest, members, version)
            status = "verified" if version == SCHEMA_VERSION else "legacy_verified"
            return {
                "backup_sha256": _sha256_file(archive_path),
                "restore_engine_version": SCHEMA_VERSION,
                "verified_at": self._clock().isoformat(),
                "status": status,
                "error": None,
            }
        except SchemaIncompatibleError as exc:
            return {
                "backup_sha256": None,
                "restore_engine_version": SCHEMA_VERSION,
                "verified_at": self._clock().isoformat(),
                "status": "incompatible",
                "error": str(exc),
            }
        except Exception as exc:
            return {
                "backup_sha256": None,
                "restore_engine_version": SCHEMA_VERSION,
                "verified_at": self._clock().isoformat(),
                "status": "invalid",
                "error": str(exc) or exc.__class__.__name__,
            }

    def assert_restore_allowed(self, archive_path: str) -> dict:
        report = self.inspection(archive_path, persist=False)
        if report.get("status") not in {"verified", "legacy_verified"}:
            raise SchemaIncompatibleError(
                "backup não certificado para restore: "
                f"{report.get('status')} - {report.get('error') or 'sem detalhes'}"
            )
        return report

    def _write_verification(self, archive_path: str, report: dict) -> None:
        path = self.verification_path(archive_path)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _validate_required_content(self, manifest: dict, members: dict, version: int) -> None:
        required = {
            f"qdrant/{name}.snapshot" for name in manifest.get("collections", [])
        }
        if manifest.get("postgres", {}).get("present"):
            required.add("postgres/dump.sql.gz")
        missing = sorted(required - set(members))
        if missing:
            raise ArchiveCorruptError(
                f"partes obrigatórias ausentes: {', '.join(missing)}"
            )
        dump = members.get("postgres/dump.sql.gz")
        if dump is not None:
            try:
                gzip.decompress(dump)
            except (OSError, EOFError) as exc:
                raise ArchiveCorruptError("dump PostgreSQL gzip inválido") from exc
        for path, data in members.items():
            if path.startswith("attachments/") and path.endswith(".tar.gz"):
                try:
                    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                        tf.getmembers()
                except (tarfile.TarError, OSError, EOFError) as exc:
                    raise ArchiveCorruptError(
                        f"arquivo de anexos inválido: {path}"
                    ) from exc
        if version == SCHEMA_VERSION:
            collections = manifest.get("qdrant", {}).get("collections", {})
            if set(collections) != set(manifest.get("collections", [])):
                raise ArchiveCorruptError(
                    "inventário Qdrant divergente da lista de coleções"
                )
            for name, info in collections.items():
                if info.get("points_count") is None:
                    raise ArchiveCorruptError(
                        f"points_count ausente para coleção {name}"
                    )

    def _verify_restored_qdrant(self, manifest: dict) -> None:
        expected_by_collection = {
            name: int(info["points_count"])
            for name, info in manifest.get("qdrant", {}).get("collections", {}).items()
            if info.get("points_count") is not None
        }
        actual_by_collection = self._service.qdrant_collection_points()
        if expected_by_collection:
            if actual_by_collection != expected_by_collection:
                raise RuntimeError(
                    "Verificação pós-restore falhou no Qdrant: "
                    f"atual={actual_by_collection}, esperado={expected_by_collection}"
                )
            return
        expected_total = manifest.get("points_count")
        actual_total = sum(actual_by_collection.values()) if actual_by_collection else None
        if (
            expected_total is not None
            and actual_total is not None
            and int(actual_total) != int(expected_total)
        ):
            raise RuntimeError(
                "Verificação pós-restore falhou: "
                f"Qdrant possui {actual_total} pontos, esperado {expected_total}"
            )

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
                        **self._verification_info(path),
                    )
                )
        if self._policy.mirror_s3:
            try:
                infos.extend(self._list_s3())
            except Exception as exc:
                # Fail-open: status/list da UI e o worker não podem cair com 500
                # se o MinIO estiver com credenciais erradas — o local continua válido.
                logger.warning("backup S3 list failed (using local only): %s", exc)
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

    def _verification_info(self, path: str) -> dict:
        report = self.verification(path)
        status = report.get("status", "unverified")
        return {
            "schema_version": _read_schema_version(path),
            "verification_status": status,
            "restore_allowed": status in {"verified", "legacy_verified"},
            "verification_error": report.get("error"),
        }

    def status(self) -> dict:
        """Resumo para a UI/worker: último backup, idade (RPO), nº de cópias."""
        last_error = self._read_last_error()
        progress = _PROGRESS.to_dict()
        infos = [i for i in self.list() if i.location == "local"]
        if not infos:
            return {
                "last_backup": None,
                "rpo_age_seconds": None,
                "archives": 0,
                "last_error": last_error,
                "progress": progress,
            }
        newest = max(infos, key=lambda i: i.created_at or datetime.min.replace(tzinfo=UTC))
        age = None
        if newest.created_at is not None:
            age = (self._clock() - newest.created_at).total_seconds()
        return {
            "last_backup": newest.name,
            "rpo_age_seconds": age,
            "archives": len(infos),
            "last_error": last_error,
            "progress": progress,
        }

    def _last_error_path(self) -> str:
        return os.path.join(self._policy.local_dir, _LAST_ERROR_NAME)

    def _write_last_error(self, message: str) -> None:
        try:
            os.makedirs(self._policy.local_dir, exist_ok=True)
            with open(self._last_error_path(), "w", encoding="utf-8") as fh:
                fh.write((message or "backup failed")[:2000])
        except OSError:
            logger.warning("could not persist backup last_error", exc_info=True)

    def _clear_last_error(self) -> None:
        try:
            os.remove(self._last_error_path())
        except OSError:
            pass

    def _read_last_error(self) -> Optional[str]:
        path = self._last_error_path()
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read().strip()
            return text or None
        except OSError:
            return None

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
                    try:
                        os.remove(self.verification_path(os.path.join(local_dir, fname)))
                    except OSError:
                        pass
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


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_schema_version(zip_path: str) -> Optional[int]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read(MANIFEST_NAME))
        return manifest.get("schema_version")
    except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return None


def _read_points_count(zip_path: str) -> Optional[int]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read(MANIFEST_NAME))
        return manifest.get("points_count")
    except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return None
