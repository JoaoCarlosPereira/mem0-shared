"""Tests para o schema e a persistência da BackupPolicy (task_01 / ADR-001)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Carrega app.database (define Base e o read_audit model) ANTES de app.models,
# evitando o import circular models <-> read_audit_log_model.
from app.database import Base
from app.schemas import BackupPolicySchema
from app.utils.backup_policy import get_backup_policy, save_backup_policy


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    yield db
    db.close()
    engine.dispose()


# -- schema -----------------------------------------------------------------
def test_defaults_are_disabled():
    policy = BackupPolicySchema()
    assert policy.enabled is False
    assert policy.frequency == "daily"
    assert policy.retention == 5
    assert policy.run_at == "03:00"


def test_valid_payload_normalizes_run_at():
    policy = BackupPolicySchema(frequency="weekly", run_at="3:5", retention=10)
    assert policy.run_at == "03:05"
    assert policy.frequency == "weekly"


@pytest.mark.parametrize("retention", [0, 51, -1])
def test_retention_out_of_range_rejected(retention):
    with pytest.raises(ValidationError):
        BackupPolicySchema(retention=retention)


def test_invalid_timezone_rejected():
    with pytest.raises(ValidationError):
        BackupPolicySchema(timezone="Marte/Olimpo")


def test_invalid_frequency_rejected():
    with pytest.raises(ValidationError):
        BackupPolicySchema(frequency="hourly")


@pytest.mark.parametrize("run_at", ["25:99", "3", "ab:cd", "10:60"])
def test_invalid_run_at_rejected(run_at):
    with pytest.raises(ValidationError):
        BackupPolicySchema(run_at=run_at)


# -- persistência -----------------------------------------------------------
def test_get_returns_defaults_when_absent(session):
    policy = get_backup_policy(session)
    assert policy.enabled is False
    assert policy.retention == 5


def test_save_and_read_round_trip(session):
    saved = save_backup_policy(
        session,
        BackupPolicySchema(
            enabled=True,
            frequency="weekly",
            run_at="02:30",
            timezone="America/Sao_Paulo",
            local_dir="/mnt/backups",
            retention=7,
            mirror_s3=True,
        ),
    )
    assert saved.enabled is True
    read = get_backup_policy(session)
    assert read.frequency == "weekly"
    assert read.run_at == "02:30"
    assert read.retention == 7
    assert read.mirror_s3 is True


def test_save_is_upsert(session):
    save_backup_policy(session, BackupPolicySchema(retention=5))
    save_backup_policy(session, BackupPolicySchema(retention=9))
    assert get_backup_policy(session).retention == 9
