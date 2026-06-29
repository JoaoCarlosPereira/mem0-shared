"""Validação dos arquivos de orquestração para o backup-worker (task_06 / ADR-002).

Confere que o serviço openmemory-backup-worker existe no compose e no stack Swarm,
com o comando correto e o volume de backup montado, sem alterar os volumes
existentes (mem0_storage).
"""

import pytest

from tests.paths import openmemory_root

yaml = pytest.importorskip("yaml")

ROOT = openmemory_root()
COMPOSE = ROOT / "docker-compose.scale.yml"
STACK = ROOT / "docker-stack.yml"


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def stack():
    return yaml.safe_load(STACK.read_text(encoding="utf-8"))


# -- docker-compose.scale.yml ----------------------------------------------
def test_compose_backup_worker_exists_with_command(compose):
    svc = compose["services"]["openmemory-backup-worker"]
    assert svc["command"] == "python -m app.workers.backup_worker"


def test_compose_backup_volume_mounted_on_api_and_worker(compose):
    target = "/mnt/backups"
    api_vols = compose["services"]["openmemory-mcp"]["volumes"]
    worker_vols = compose["services"]["openmemory-backup-worker"]["volumes"]
    assert any(str(v).endswith(target) for v in api_vols)
    assert any(str(v).endswith(target) for v in worker_vols)


def test_compose_qdrant_volume_unchanged(compose):
    # O volume de dados do Qdrant não pode ter sido alterado por esta task.
    qdrant_vols = compose["services"]["mem0_store"]["volumes"]
    assert any("mem0_storage" in str(v) and "/qdrant/storage" in str(v) for v in qdrant_vols)


# -- docker-stack.yml (Swarm) ----------------------------------------------
def test_stack_backup_worker_exists_with_command(stack):
    svc = stack["services"]["openmemory-backup-worker"]
    assert svc["command"] == "python -m app.workers.backup_worker"
    assert svc["deploy"]["replicas"] == 1


def test_stack_backup_volume_declared_and_mounted(stack):
    assert "mem0_backups" in stack["volumes"]
    worker_vols = stack["services"]["openmemory-backup-worker"]["volumes"]
    assert any("mem0_backups" in str(v) for v in worker_vols)


def test_stack_qdrant_volume_unchanged(stack):
    assert "mem0_storage" in stack["volumes"]
    qdrant_vols = stack["services"]["mem0_store"]["volumes"]
    assert any("mem0_storage" in str(v) for v in qdrant_vols)
