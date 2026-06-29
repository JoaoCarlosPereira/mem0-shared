"""Tests para o restore via BackupArchive (task_03 / ADR-003, ADR-005).

Inclui o round-trip backup→restore com um Qdrant stateful (sem infraestrutura
real). A verificação ao vivo (MinIO + Qdrant + PostgreSQL) é o drill manual
documentado em scripts/ — alinhado à convenção do repo (ver app/utils/backup.py).
"""

import json
import os
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


def _archive(tmp_path, qc, *, db_url="sqlite:///x.db", retention=5):
    svc = BackupService(
        s3_client=FakeS3(),
        bucket="b",
        db_url=db_url,
        qdrant_client_provider=lambda: qc,
        pg_dump_runner=lambda url: __import__("gzip").compress(b"PGDUMP"),
    )
    policy = BackupPolicySchema(local_dir=str(tmp_path), retention=retention)
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
    assert any(f.startswith("pre-restore-") for f in os.listdir(tmp_path))


def test_restore_skips_safety_snapshot_when_disabled(tmp_path):
    qc = StatefulQdrant({"c1": 5})
    arc = _archive(tmp_path, qc)
    archive = arc.create()
    before = {f for f in os.listdir(tmp_path)}
    arc.restore(archive.path, safety_snapshot=False)
    after = {f for f in os.listdir(tmp_path)}
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
    assert calls.get("psql_input") == b"PGDUMP"  # dump descomprimido aplicado via psql
    assert qc.store["c1"] == 3
