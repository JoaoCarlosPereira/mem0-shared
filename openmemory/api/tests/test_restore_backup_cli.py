"""Tests para a CLI de restore na instalação (task_07 / ADR-004)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

# Carrega app.database antes de app.models (evita import circular).
from app.database import Base  # noqa: F401
from app.scripts import restore_backup
from app.utils.backup_archive import ArchiveCorruptError, SchemaIncompatibleError


class FakeArchive:
    def __init__(self):
        self.restored = None

    def restore(self, path, *, safety_snapshot=True):
        self.restored = (path, safety_snapshot)
        return {"postgres": "postgres/dump.sql.gz", "qdrant": ["c1"]}


def test_run_restore_uses_no_safety_snapshot():
    fake = FakeArchive()
    out = restore_backup.run_restore("/x/backup.zip", build=lambda: fake)
    assert fake.restored == ("/x/backup.zip", False)
    assert out["qdrant"] == ["c1"]


def test_main_success_returns_0():
    fake = FakeArchive()
    rc = restore_backup.main(["/x/backup.zip"], build=lambda: fake)
    assert rc == 0
    assert fake.restored[0] == "/x/backup.zip"


def test_main_missing_file_returns_2():
    def build():
        raise FileNotFoundError("/x/nope.zip")

    rc = restore_backup.main(["/x/nope.zip"], build=build)
    assert rc == 2


def test_main_incompatible_returns_3():
    def build():
        raise SchemaIncompatibleError("schema 999")

    rc = restore_backup.main(["/x/old.zip"], build=build)
    assert rc == 3


def test_main_corrupt_returns_4():
    def build():
        raise ArchiveCorruptError("checksum")

    rc = restore_backup.main(["/x/bad.zip"], build=build)
    assert rc == 4


def test_main_requires_archive_arg():
    with pytest.raises(SystemExit):
        restore_backup.main([])
