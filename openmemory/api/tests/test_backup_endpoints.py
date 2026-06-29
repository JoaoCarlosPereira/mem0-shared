"""Tests para os endpoints /admin/backup/* (task_04 / ADR-003, ADR-005).

Path-load do módulo admin.py (evita o __init__ pesado do pacote app.routers, que
importa mem0). Os endpoints de backup operam sobre BackupArchive (override de
dependência) e a política via SQLite em memória (override de get_db).
"""

import importlib.util
import os
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Carrega app.database (Base/get_db) antes de path-load do admin.
from app.database import Base, get_db
from app.schemas import BackupArchiveInfo

_PATH = Path(__file__).resolve().parents[1] / "app" / "routers" / "admin.py"
_spec = importlib.util.spec_from_file_location("admin_backup_under_test", _PATH)
_admin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_admin)
router = _admin.router


class FakeArchive:
    def __init__(self, exists=True):
        self._exists = exists
        self.created = False
        self.restored = None

    def create(self):
        self.created = True

    def status(self):
        return {"last_backup": "20260618-030000.zip", "rpo_age_seconds": 3600, "archives": 3, "last_error": None}

    def list(self):
        return [BackupArchiveInfo(name="20260618-030000.zip", size=10, points_count=6, location="local")]

    def has(self, name):
        return self._exists

    def path_for(self, name):
        return f"/mnt/backups/{name}"

    def restore(self, path):
        self.restored = path


@pytest.fixture
def ctx():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    fake = FakeArchive()
    app = FastAPI()
    app.include_router(router)

    def _db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[_admin._backup_archive] = lambda: fake
    yield app, fake
    engine.dispose()


def test_backup_run_returns_202_and_triggers(ctx):
    app, fake = ctx
    with TestClient(app) as client:
        resp = client.post("/admin/backup/run")
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"
    assert fake.created is True


def test_backup_status_returns_rpo_and_archives(ctx):
    app, _ = ctx
    with TestClient(app) as client:
        resp = client.get("/admin/backup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["archives"] == 3
    assert body["rpo_age_seconds"] == 3600
    assert body["last_backup"] == "20260618-030000.zip"


def test_backup_list_returns_archives(ctx):
    app, _ = ctx
    with TestClient(app) as client:
        resp = client.get("/admin/backup/list")
    assert resp.status_code == 200
    archives = resp.json()["archives"]
    assert len(archives) == 1
    assert archives[0]["points_count"] == 6


def test_policy_get_returns_defaults(ctx):
    app, _ = ctx
    with TestClient(app) as client:
        resp = client.get("/admin/backup/policy")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["retention"] == 5


def test_policy_put_persists_valid(ctx, tmp_path):
    app, _ = ctx
    payload = {
        "enabled": True,
        "frequency": "weekly",
        "run_at": "02:30",
        "timezone": "America/Sao_Paulo",
        "local_dir": str(tmp_path),
        "retention": 7,
        "mirror_s3": False,
    }
    with TestClient(app) as client:
        resp = client.put("/admin/backup/policy", json=payload)
        assert resp.status_code == 200
        assert resp.json()["retention"] == 7
        again = client.get("/admin/backup/policy")
    assert again.json()["frequency"] == "weekly"


def test_policy_put_invalid_retention_returns_400(ctx, tmp_path):
    app, _ = ctx
    with TestClient(app) as client:
        resp = client.put(
            "/admin/backup/policy",
            json={"retention": 51, "local_dir": str(tmp_path)},
        )
    assert resp.status_code == 400


def test_policy_put_invalid_timezone_returns_400(ctx, tmp_path):
    app, _ = ctx
    with TestClient(app) as client:
        resp = client.put(
            "/admin/backup/policy",
            json={"timezone": "Marte/Olimpo", "local_dir": str(tmp_path)},
        )
    assert resp.status_code == 400


def test_restore_confirm_mismatch_returns_400(ctx):
    app, fake = ctx
    with TestClient(app) as client:
        resp = client.post(
            "/admin/backup/restore",
            json={"archive": "20260618-030000.zip", "confirm": "errado"},
        )
    assert resp.status_code == 400
    assert fake.restored is None


def test_restore_missing_archive_returns_404():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    fake = FakeArchive(exists=False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[_admin._backup_archive] = lambda: fake
    with TestClient(app) as client:
        resp = client.post(
            "/admin/backup/restore",
            json={"archive": "nope.zip", "confirm": "nope.zip"},
        )
    assert resp.status_code == 404
    assert fake.restored is None
    engine.dispose()


def test_restore_valid_returns_202_and_triggers(ctx):
    app, fake = ctx
    with TestClient(app) as client:
        resp = client.post(
            "/admin/backup/restore",
            json={"archive": "20260618-030000.zip", "confirm": "20260618-030000.zip"},
        )
    assert resp.status_code == 202
    assert fake.restored == "/mnt/backups/20260618-030000.zip"
