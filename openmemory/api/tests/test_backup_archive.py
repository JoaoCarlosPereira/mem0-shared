"""Tests para a camada BackupArchive (task_02 / ADR-003).

Empacotamento .zip + manifest, espelhamento S3 e rotação FIFO, exercitados com
Qdrant/PostgreSQL/S3 e relógio mockados (sem infraestrutura real).
"""

import gzip
import hashlib
import io
import json
import os
import zipfile
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.utils.backup import BackupService
from app.utils.backup_archive import BackupArchive
from app.utils.metrics import BACKUP_ERRORS_TOTAL
from app.schemas import BackupPolicySchema

_PG_URL = "postgresql://u:p@db:5432/mem0"


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body):
        self.objects[Key] = Body

    def list_objects_v2(self, *, Bucket, Prefix):
        return {
            "Contents": [
                {"Key": k, "LastModified": datetime(2026, 6, 18, tzinfo=UTC), "Size": len(v)}
                for k, v in self.objects.items()
                if k.startswith(Prefix)
            ]
        }

    def get_object(self, *, Bucket, Key):
        return {"Body": SimpleNamespace(read=lambda: self.objects[Key])}

    def delete_object(self, *, Bucket, Key):
        self.objects.pop(Key, None)


class FakeQdrant:
    def __init__(self, collections=("c1", "c2"), points=3):
        self._cols = collections
        self._points = points

    def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name=n) for n in self._cols])

    def create_snapshot(self, *, collection_name):
        return SimpleNamespace(name=f"{collection_name}-snap")

    def download_snapshot(self, *, collection_name, snapshot_name):
        return f"data-{collection_name}".encode()

    def get_collection(self, name):
        return SimpleNamespace(points_count=self._points)


class IncClock:
    """Relógio que avança 1s por chamada (nomes de arquivo distintos)."""

    def __init__(self, start=datetime(2026, 6, 18, 0, 0, 0, tzinfo=UTC)):
        self.t = start

    def __call__(self):
        self.t = self.t + timedelta(seconds=1)
        return self.t


def _service(s3, qc):
    return BackupService(
        s3_client=s3,
        bucket="b",
        db_url=_PG_URL,
        qdrant_client_provider=lambda: qc,
        pg_dump_runner=lambda url: gzip.compress(b"PGDUMP"),
    )


def _archive(tmp_path, s3, qc, *, retention=5, mirror_s3=False, clock=None):
    policy = BackupPolicySchema(
        local_dir=str(tmp_path), retention=retention, mirror_s3=mirror_s3
    )
    return BackupArchive(
        _service(s3, qc), policy, clock=clock or IncClock(), openmemory_version="test"
    )


def test_create_produces_zip_with_three_part_groups(tmp_path):
    arc = _archive(tmp_path, FakeS3(), FakeQdrant())
    result = arc.create()
    assert os.path.exists(result.path)
    with zipfile.ZipFile(result.path) as zf:
        names = set(zf.namelist())
    assert names == {
        "manifest.json",
        "qdrant/c1.snapshot",
        "qdrant/c2.snapshot",
        "postgres/dump.sql.gz",
    }


def test_manifest_has_correct_checksums_and_points(tmp_path):
    arc = _archive(tmp_path, FakeS3(), FakeQdrant(points=3))
    result = arc.create()
    with zipfile.ZipFile(result.path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        snap = zf.read("qdrant/c1.snapshot")
    assert manifest["points_count"] == 6  # 2 coleções x 3 pontos
    assert manifest["schema_version"] == 1
    part = next(p for p in manifest["parts"] if p["path"] == "qdrant/c1.snapshot")
    assert part["sha256"] == hashlib.sha256(snap).hexdigest()


def test_mirror_s3_uploads_same_zip(tmp_path):
    s3 = FakeS3()
    arc = _archive(tmp_path, s3, FakeQdrant(), mirror_s3=True)
    result = arc.create()
    mirrored = s3.objects[f"archives/{result.name}"]
    with open(result.path, "rb") as fh:
        assert mirrored == fh.read()


def test_no_mirror_when_disabled(tmp_path):
    s3 = FakeS3()
    arc = _archive(tmp_path, s3, FakeQdrant(), mirror_s3=False)
    arc.create()
    assert s3.objects == {}


def test_fifo_keeps_retention_and_drops_oldest(tmp_path):
    clock = IncClock()
    arc = _archive(tmp_path, FakeS3(), FakeQdrant(), retention=5, clock=clock)
    names = [arc.create().name for _ in range(6)]
    remaining = sorted(f for f in os.listdir(tmp_path) if f.endswith(".zip"))
    assert len(remaining) == 5
    assert names[0] not in remaining  # a mais antiga foi removida
    assert names[-1] in remaining


def test_tagged_archive_excluded_from_rotation(tmp_path):
    clock = IncClock()
    arc = _archive(tmp_path, FakeS3(), FakeQdrant(), retention=1, clock=clock)
    regular = arc.create().name
    pre = arc.create(tag="pre-restore").name
    files = set(os.listdir(tmp_path))
    # pre-restore não dispara prune do regular; ambos permanecem.
    assert regular in files
    assert pre in files
    assert pre.startswith("pre-restore-")


def test_create_failure_increments_metric_and_cleans_temp(tmp_path):
    def boom(url):
        raise RuntimeError("pg_dump down")

    svc = BackupService(
        s3_client=FakeS3(),
        bucket="b",
        db_url=_PG_URL,
        qdrant_client_provider=lambda: FakeQdrant(),
        pg_dump_runner=boom,
    )
    policy = BackupPolicySchema(local_dir=str(tmp_path), retention=5)
    arc = BackupArchive(svc, policy, clock=IncClock(), openmemory_version="test")

    before = BACKUP_ERRORS_TOTAL._value.get()
    with pytest.raises(RuntimeError):
        arc.create()
    assert BACKUP_ERRORS_TOTAL._value.get() == before + 1
    # nenhum .zip nem .tmp deixado para trás
    assert [f for f in os.listdir(tmp_path)] == []


def test_list_returns_local_archives(tmp_path):
    arc = _archive(tmp_path, FakeS3(), FakeQdrant())
    arc.create()
    arc.create()
    infos = arc.list()
    assert len(infos) == 2
    assert all(i.location == "local" for i in infos)
    assert all(i.points_count == 6 for i in infos)
