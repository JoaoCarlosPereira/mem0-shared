"""Tests para o restore via BackupArchive (task_03 / ADR-003, ADR-005).

Inclui o round-trip backup→restore com um Qdrant stateful (sem infraestrutura
real). A verificação ao vivo (MinIO + Qdrant + PostgreSQL) é o drill manual
documentado em scripts/ — alinhado à convenção do repo (ver app/utils/backup.py).
"""

import json
import os
import subprocess
import zipfile
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.utils.backup import BackupService
from app.utils.backup_archive import (
    ArchiveCorruptError,
    BackupArchive,
    SchemaIncompatibleError,
)
from app.utils.backup_attachments import PLANKA_ARCNAME, SPEC_ARCNAME
from app.schemas import BackupPolicySchema

_PG_URL = "postgresql://u:p@db:5432/mem0"


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body):
        self.objects[Key] = Body

    def list_objects_v2(self, *, Bucket, Prefix):
        return {"Contents": []}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)


class StatefulQdrant:
    """Qdrant simulado com estado: contagem de pontos por coleção."""

    def __init__(self, store=None):
        self.store = dict(store or {"c1": 5})
        self.recovered = []

    def get_collections(self):
        return SimpleNamespace(
            collections=[SimpleNamespace(name=n) for n in self.store]
        )

    def create_snapshot(self, *, collection_name):
        return SimpleNamespace(name=f"{collection_name}-snap")

    def download_snapshot(self, *, collection_name, snapshot_name):
        return str(self.store[collection_name]).encode()

    def get_collection(self, name):
        return SimpleNamespace(points_count=self.store[name])

    def recover_snapshot(self, *, collection_name, location):
        self.store[collection_name] = int(location)
        self.recovered.append(collection_name)


class IncClock:
    def __init__(self, start=datetime(2026, 6, 18, 0, 0, 0, tzinfo=UTC)):
        self.t = start

    def __call__(self):
        self.t = self.t + timedelta(seconds=1)
        return self.t


def _att_roots(tmp_path):
    spec = tmp_path / "spec-att"
    planka = tmp_path / "planka-att"
    spec.mkdir(exist_ok=True)
    planka.mkdir(exist_ok=True)
    return {SPEC_ARCNAME: spec, PLANKA_ARCNAME: planka}


def _archive(tmp_path, qc, *, db_url="sqlite:///x.db", retention=5):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    svc = BackupService(
        s3_client=FakeS3(),
        bucket="b",
        db_url=db_url,
        qdrant_client_provider=lambda: qc,
        pg_dump_runner=lambda url: __import__("gzip").compress(b"PGDUMP"),
        attachment_roots=_att_roots(tmp_path),
    )
    policy = BackupPolicySchema(local_dir=str(backup_dir), retention=retention)
    return BackupArchive(svc, policy, clock=IncClock(), openmemory_version="test")


# -- validação --------------------------------------------------------------
def _write_zip(path, members: dict, manifest: dict):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for name, data in members.items():
            zf.writestr(name, data)


def test_incompatible_schema_raises_and_no_data_touched(tmp_path):
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    bad = os.path.join(tmp_path, "bad.zip")
    _write_zip(bad, {"qdrant/c1.snapshot": b"9"}, {"schema_version": 999, "parts": []})
    with pytest.raises(SchemaIncompatibleError):
        arc.restore(bad, safety_snapshot=False)
    assert qc.recovered == []  # nada foi tocado


def test_corrupt_checksum_raises(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant())
    bad = os.path.join(tmp_path, "bad.zip")
    manifest = {
        "schema_version": 1,
        "parts": [{"path": "qdrant/c1.snapshot", "size": 1, "sha256": "deadbeef"}],
    }
    _write_zip(bad, {"qdrant/c1.snapshot": b"9"}, manifest)
    with pytest.raises(ArchiveCorruptError):
        arc.restore(bad, safety_snapshot=False)


def test_missing_archive_raises(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant())
    with pytest.raises(FileNotFoundError):
        arc.restore(os.path.join(tmp_path, "nope.zip"))


def test_manifest_missing_raises_corrupt(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant())
    bad = os.path.join(tmp_path, "nomani.zip")
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("qdrant/c1.snapshot", b"9")
    with pytest.raises(ArchiveCorruptError):
        arc.restore(bad, safety_snapshot=False)


def test_created_archive_is_certified_and_bound_to_sha256(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant({"c1": 5}))
    archive = arc.create()

    report = arc.verification(archive.path)

    assert report["status"] == "verified"
    assert archive.verification_status == "verified"
    assert len(report["backup_sha256"]) == 64
    assert os.path.exists(arc.verification_path(archive.path))


def test_legacy_v1_archive_is_certified_by_adapter(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant({"c1": 5}))
    path = os.path.join(tmp_path, "legacy.zip")
    snapshot = b"5"
    manifest = {
        "schema_version": 1,
        "collections": ["c1"],
        "points_count": 5,
        "parts": [
            {
                "path": "qdrant/c1.snapshot",
                "size": len(snapshot),
                "sha256": __import__("hashlib").sha256(snapshot).hexdigest(),
            }
        ],
    }
    _write_zip(path, {"qdrant/c1.snapshot": snapshot}, manifest)

    assert arc.assert_restore_allowed(path)["status"] == "legacy_verified"


def test_changed_archive_invalidates_previous_certification(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant({"c1": 5}))
    archive = arc.create()
    first = arc.verification(archive.path)
    assert first["status"] == "verified"

    with open(archive.path, "ab") as fh:
        fh.write(b"tampered")

    second = arc.verification(archive.path)
    assert second["backup_sha256"] != first["backup_sha256"]


def test_restore_inspection_does_not_require_writable_sidecar(tmp_path, monkeypatch):
    arc = _archive(tmp_path, StatefulQdrant({"c1": 5}))
    archive = arc.create()
    monkeypatch.setattr(
        arc,
        "_write_verification",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("read-only")),
    )

    assert arc.assert_restore_allowed(archive.path)["status"] == "verified"


def test_manifest_v2_rejects_missing_collection_inventory(tmp_path):
    arc = _archive(tmp_path, StatefulQdrant({"c1": 5}))
    path = os.path.join(tmp_path, "invalid-v2.zip")
    snapshot = b"5"
    manifest = {
        "schema_version": 2,
        "collections": ["c1"],
        "qdrant": {"collections": {}},
        "parts": [
            {
                "path": "qdrant/c1.snapshot",
                "size": len(snapshot),
                "sha256": __import__("hashlib").sha256(snapshot).hexdigest(),
            }
        ],
    }
    _write_zip(path, {"qdrant/c1.snapshot": snapshot}, manifest)

    with pytest.raises(SchemaIncompatibleError, match="não certificado"):
        arc.assert_restore_allowed(path)


# -- snapshot de segurança + ordem -----------------------------------------
def test_safety_snapshot_created_before_apply(tmp_path):
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    archive = arc.create()  # backup regular

    order = []
    orig_create = arc.create
    arc.create = lambda **kw: order.append("snapshot") or orig_create(**kw)  # type: ignore
    orig_recover = qc.recover_snapshot
    qc.recover_snapshot = lambda **kw: order.append("recover") or orig_recover(**kw)

    arc.restore(archive.path, safety_snapshot=True)
    assert order[0] == "snapshot"
    assert "recover" in order
    assert order.index("snapshot") < order.index("recover")
    # o pre-restore não conta na FIFO (regular + pre-restore presentes)
    assert any(f.startswith("pre-restore-") for f in os.listdir(tmp_path / "backups"))


def test_safety_snapshot_is_validated_before_apply(tmp_path, monkeypatch):
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    archive = arc.create()
    original_validate = arc._read_validated_members
    validated = []

    def validate(path):
        validated.append(os.path.basename(path))
        if os.path.basename(path).startswith("pre-restore-"):
            raise ArchiveCorruptError("snapshot de segurança inválido")
        return original_validate(path)

    monkeypatch.setattr(arc, "_read_validated_members", validate)
    with pytest.raises(ArchiveCorruptError, match="snapshot de segurança inválido"):
        arc.restore(archive.path, safety_snapshot=True)
    assert any(name.startswith("pre-restore-") for name in validated)
    assert qc.recovered == []


def test_restore_skips_safety_snapshot_when_disabled(tmp_path):
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    archive = arc.create()
    before = {f for f in os.listdir(tmp_path / "backups")}
    arc.restore(archive.path, safety_snapshot=False)
    after = {f for f in os.listdir(tmp_path / "backups")}
    assert not any(f.startswith("pre-restore-") for f in after - before)


def test_restore_does_not_use_deletion_guard(tmp_path, monkeypatch):
    # Se o restore tocasse a guarda, importar/assert lançaria; garantimos que não há chamada.
    import app.utils.deletion_guard as guard

    called = {"n": 0}
    monkeypatch.setattr(guard, "assert_memory_delete_allowed", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr(guard, "assert_bulk_delete_allowed", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    archive = arc.create()
    arc.restore(archive.path, safety_snapshot=False)
    assert called["n"] == 0


# -- round-trip -------------------------------------------------------------
def test_round_trip_restores_points_count(tmp_path):
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    archive = arc.create()
    assert archive.points_count == 5

    # "desastre": zera a coleção
    qc.store["c1"] = 0
    out = arc.restore(archive.path, safety_snapshot=False)

    assert out["qdrant"] == ["c1"]
    assert qc.store["c1"] == 5  # estado original recuperado
    assert qc.recovered == ["c1"]


def test_recover_qdrant_snapshot_uses_http_upload_for_real_client(monkeypatch):
    import app.utils.backup as bmod

    calls = {}
    qc = object()
    monkeypatch.setattr(bmod, "_is_real_qdrant_client", lambda value: value is qc)
    monkeypatch.setattr(
        bmod,
        "_upload_qdrant_snapshot_http",
        lambda name, data: calls.update(name=name, data=data),
    )
    svc = BackupService(s3_client=FakeS3(), bucket="b", qdrant_client_provider=lambda: qc)

    svc.recover_qdrant_snapshot("openmemory", b"snapshot", qc=qc)

    assert calls == {"name": "openmemory", "data": b"snapshot"}


def test_round_trip_with_postgres_applies_dump(tmp_path, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "app.utils.backup.subprocess.run",
        lambda *a, **k: calls.setdefault("psql_input", k.get("input")),
    )
    qc = StatefulQdrant({"c1": 3})
    arc = _archive(tmp_path, qc, db_url=_PG_URL)
    archive = arc.create()
    qc.store["c1"] = 0
    out = arc.restore(archive.path, safety_snapshot=False)
    assert out["postgres"] == "postgres/dump.sql.gz"
    assert b"PGDUMP" in calls.get("psql_input", b"")
    assert b'DROP SCHEMA IF EXISTS "public" CASCADE;' in calls["psql_input"]
    assert qc.store["c1"] == 3


# -- timeout dos subprocessos bloqueantes (regressão do deadlock 2026-08-17) --
def test_apply_pg_dump_passes_timeout_to_psql(monkeypatch):
    import app.utils.backup as bmod

    calls = {}
    monkeypatch.setattr(
        bmod.subprocess,
        "run",
        lambda *a, **k: calls.setdefault("kwargs", k),
    )
    svc = BackupService(s3_client=FakeS3(), bucket="b", db_url=_PG_URL)
    svc.apply_pg_dump(__import__("gzip").compress(b"SELECT 1;"))
    timeout = calls["kwargs"].get("timeout")
    assert timeout == bmod.BACKUP_PG_TIMEOUT
    assert timeout is not None and timeout > 0


def test_default_pg_dump_passes_timeout_to_subprocess(monkeypatch):
    import app.utils.backup as bmod

    calls = {}
    monkeypatch.setattr(
        bmod.subprocess,
        "run",
        lambda *a, **k: (
            calls.update(args=a[0], kwargs=k),
            SimpleNamespace(stdout=b"x"),
        )[1],
    )
    bmod._default_pg_dump(_PG_URL)
    assert calls["kwargs"].get("timeout") == bmod.BACKUP_PG_TIMEOUT
    assert calls["kwargs"]["timeout"] > 0
    assert calls["args"] == [
        "pg_dump",
        "--dbname",
        _PG_URL,
        "--no-owner",
        "--no-acl",
    ]


def test_pg_dump_sanitizes_transaction_timeout():
    import app.utils.backup as bmod

    sql = b"SET transaction_timeout = 600000;\nSELECT 1;\n"
    assert bmod._sanitize_pg_dump(sql) == b"SELECT 1;\n"


def test_apply_pg_dump_is_fail_fast_and_sanitizes_sql(monkeypatch):
    import app.utils.backup as bmod

    calls = {}
    monkeypatch.setattr(
        bmod.subprocess,
        "run",
        lambda *a, **k: calls.update(args=a[0], kwargs=k),
    )
    svc = BackupService(s3_client=FakeS3(), bucket="b", db_url=_PG_URL)
    svc.apply_pg_dump(__import__("gzip").compress(b"SET transaction_timeout = 1;\nSELECT 1;\n"))

    assert calls["args"] == [
        "psql",
        "--dbname",
        _PG_URL,
        "--single-transaction",
        "--set",
        "ON_ERROR_STOP=1",
    ]
    assert b"SELECT 1;\n" in calls["kwargs"]["input"]
    assert b"transaction_timeout" not in calls["kwargs"]["input"]
    assert b"ALTER DATABASE %I SET search_path TO public" in calls["kwargs"]["input"]
    assert calls["kwargs"]["capture_output"] is True


def test_apply_pg_dump_replaces_managed_schemas_in_same_transaction(monkeypatch):
    import app.utils.backup as bmod

    calls = {}
    monkeypatch.setattr(
        bmod.subprocess,
        "run",
        lambda *a, **k: calls.update(args=a[0], kwargs=k),
    )
    dump = b"\n".join(
        [
            b"CREATE SCHEMA agentregistry;",
            b"CREATE SCHEMA planka;",
            b"CREATE TABLE public.memories (id integer);",
        ]
    )
    svc = BackupService(s3_client=FakeS3(), bucket="b", db_url=_PG_URL)
    svc.apply_pg_dump(__import__("gzip").compress(dump))

    sql = calls["kwargs"]["input"]
    assert sql.startswith(
        b'DROP SCHEMA IF EXISTS "agentregistry" CASCADE;\n'
        b'DROP SCHEMA IF EXISTS "planka" CASCADE;\n'
        b'DROP SCHEMA IF EXISTS "public" CASCADE;\n'
        b'CREATE SCHEMA "public";\n'
    )
    assert dump in sql
    assert b"20260812000000_add_board_creator_user.js" in sql
    assert calls["args"][-2:] == ["--set", "ON_ERROR_STOP=1"]


def test_apply_pg_dump_reconnects_pgbouncer_after_success(monkeypatch):
    import app.utils.backup as bmod

    calls = []
    monkeypatch.setattr(
        bmod.subprocess,
        "run",
        lambda *a, **k: calls.append((a[0], k)),
    )
    svc = BackupService(
        s3_client=FakeS3(),
        bucket="b",
        db_url="postgresql://u:p@pgbouncer:5432/openmemory",
    )

    svc.apply_pg_dump(__import__("gzip").compress(b"SELECT 1;\n"))

    assert len(calls) == 2
    assert calls[1][0] == [
        "psql",
        "--dbname",
        "postgresql://u:p@pgbouncer:5432/pgbouncer",
        "--set",
        "ON_ERROR_STOP=1",
        "--command",
        "RECONNECT openmemory;",
    ]


def test_apply_pg_dump_skips_reconnect_for_direct_postgres(monkeypatch):
    import app.utils.backup as bmod

    calls = []
    monkeypatch.setattr(
        bmod.subprocess,
        "run",
        lambda *a, **k: calls.append((a[0], k)),
    )
    svc = BackupService(
        s3_client=FakeS3(),
        bucket="b",
        db_url="postgresql://u:p@postgres:5432/openmemory",
    )

    svc.apply_pg_dump(__import__("gzip").compress(b"SELECT 1;\n"))

    assert len(calls) == 1


def test_apply_pg_dump_surfaces_sanitized_psql_error(monkeypatch):
    import app.utils.backup as bmod

    db_url = "postgresql://sysdba:secret@pgbouncer:5432/openmemory"

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(
            3,
            args[0],
            stderr=b'ERROR:  relation "memories" already exists\n',
        )

    monkeypatch.setattr(bmod.subprocess, "run", fail)
    svc = BackupService(s3_client=FakeS3(), bucket="b", db_url=db_url)

    with pytest.raises(RuntimeError) as excinfo:
        svc.apply_pg_dump(__import__("gzip").compress(b"SELECT 1;\n"))
    message = str(excinfo.value)
    assert 'relation "memories" already exists' in message
    assert "secret" not in message
    assert db_url not in message


def test_backup_pg_timeout_env_override(monkeypatch):
    import importlib

    import app.utils.backup as bmod

    monkeypatch.setenv("BACKUP_PG_TIMEOUT", "42")
    importlib.reload(bmod)
    assert bmod.BACKUP_PG_TIMEOUT == 42
    monkeypatch.delenv("BACKUP_PG_TIMEOUT", raising=False)
    importlib.reload(bmod)
    assert bmod.BACKUP_PG_TIMEOUT == 600


def test_round_trip_restores_attachment_files(tmp_path):
    roots = _att_roots(tmp_path)
    (roots[SPEC_ARCNAME] / "task1").mkdir()
    (roots[SPEC_ARCNAME] / "task1" / "a.txt").write_text("spec-data", encoding="utf-8")
    (roots[PLANKA_ARCNAME] / "private").mkdir()
    (roots[PLANKA_ARCNAME] / "private" / "b.bin").write_bytes(b"\x00planka")

    qc = StatefulQdrant({"c1": 2})
    arc = _archive(tmp_path, qc)
    archive = arc.create()

    # desastre nos volumes
    (roots[SPEC_ARCNAME] / "task1" / "a.txt").write_text("gone", encoding="utf-8")
    (roots[PLANKA_ARCNAME] / "private" / "b.bin").unlink()
    (roots[SPEC_ARCNAME] / "orphan.txt").write_text("should-vanish", encoding="utf-8")

    out = arc.restore(archive.path, safety_snapshot=False)
    assert SPEC_ARCNAME in out["attachments"]
    assert PLANKA_ARCNAME in out["attachments"]
    assert (roots[SPEC_ARCNAME] / "task1" / "a.txt").read_text(encoding="utf-8") == "spec-data"
    assert (roots[PLANKA_ARCNAME] / "private" / "b.bin").read_bytes() == b"\x00planka"
    assert not (roots[SPEC_ARCNAME] / "orphan.txt").exists()


def test_legacy_zip_without_attachments_still_restores_qdrant(tmp_path):
    """Zips schema v1 sem attachments/*.tar.gz continuam válidos."""
    import hashlib

    qc = StatefulQdrant({"c1": 5})
    snap = b"5"
    legacy = tmp_path / "backups"
    legacy.mkdir(exist_ok=True)
    path = legacy / "legacy.zip"
    manifest = {
        "schema_version": 1,
        "parts": [
            {
                "path": "qdrant/c1.snapshot",
                "size": len(snap),
                "sha256": hashlib.sha256(snap).hexdigest(),
            }
        ],
    }
    _write_zip(str(path), {"qdrant/c1.snapshot": snap}, manifest)

    arc = _archive(tmp_path, qc)
    qc.store["c1"] = 0
    out = arc.restore(str(path), safety_snapshot=False)
    assert out["qdrant"] == ["c1"]
    assert out["attachments"] == []
    assert qc.store["c1"] == 5
