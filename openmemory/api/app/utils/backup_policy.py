"""Persistência da política de backup em ``Config(key="backup_policy")`` (task_01).

Reaproveita a tabela ``Config`` existente (ADR-001) em vez de criar tabela/migração
nova. Os helpers recebem a sessão SQLAlchemy e operam sobre uma única linha JSON,
retornando sempre uma ``BackupPolicySchema`` validada (defaults quando ausente).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Config as ConfigModel
from app.models import get_current_utc_time
from app.schemas import BackupPolicySchema

BACKUP_POLICY_KEY = "backup_policy"


def get_backup_policy(db: Session) -> BackupPolicySchema:
    """Lê a política de backup; retorna defaults (``enabled=False``) se inexistente."""
    row = db.query(ConfigModel).filter(ConfigModel.key == BACKUP_POLICY_KEY).first()
    if row is None or not row.value:
        return BackupPolicySchema()
    return BackupPolicySchema(**row.value)


def save_backup_policy(db: Session, policy: BackupPolicySchema) -> BackupPolicySchema:
    """Valida e persiste (upsert) a política de backup em ``Config``."""
    if not isinstance(policy, BackupPolicySchema):
        policy = BackupPolicySchema(**dict(policy))
    value = policy.model_dump()
    row = db.query(ConfigModel).filter(ConfigModel.key == BACKUP_POLICY_KEY).first()
    if row is not None:
        row.value = value
        row.updated_at = get_current_utc_time()
    else:
        row = ConfigModel(key=BACKUP_POLICY_KEY, value=value)
        db.add(row)
    db.commit()
    db.refresh(row)
    return BackupPolicySchema(**row.value)
