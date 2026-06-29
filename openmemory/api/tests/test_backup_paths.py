"""Tests for host ↔ container backup path mapping."""

import os

import pytest

from app.schemas import BackupPolicySchema
from app.utils import backup_paths


@pytest.fixture(autouse=True)
def _clear_local_backup_dir(monkeypatch):
    monkeypatch.delenv("LOCAL_BACKUP_DIR", raising=False)


def test_default_local_dir_without_env():
    assert backup_paths.default_local_dir() == "/mnt/backups"


def test_default_local_dir_uses_host_env(monkeypatch):
    monkeypatch.setenv("LOCAL_BACKUP_DIR", "/mnt/dados/backups")
    assert backup_paths.default_local_dir() == "/mnt/dados/backups"


def test_host_to_container_translation(monkeypatch):
    monkeypatch.setenv("LOCAL_BACKUP_DIR", "/mnt/dados/backups")
    assert backup_paths.to_container_path("/mnt/dados/backups") == "/mnt/backups"
    assert backup_paths.to_container_path("/mnt/backups") == "/mnt/backups"


def test_container_to_host_translation(monkeypatch):
    monkeypatch.setenv("LOCAL_BACKUP_DIR", "/mnt/dados/backups")
    assert backup_paths.to_host_path("/mnt/backups") == "/mnt/dados/backups"
    assert backup_paths.to_host_path("/tmp/custom") == "/tmp/custom"


def test_policy_round_trip(monkeypatch):
    monkeypatch.setenv("LOCAL_BACKUP_DIR", "/mnt/dados/backups")
    policy = BackupPolicySchema(local_dir="/mnt/dados/backups")
    runtime = backup_paths.internalize_policy(policy)
    assert runtime.local_dir == "/mnt/backups"
    stored = backup_paths.policy_for_storage(policy)
    assert stored.local_dir == "/mnt/dados/backups"
    api = backup_paths.externalize_policy(
        BackupPolicySchema(local_dir="/mnt/backups", enabled=True)
    )
    assert api.local_dir == "/mnt/dados/backups"
