"""Tests for governance policy resolver (task_02)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Config, GovernancePolicy, Project
from app.utils.governance_policy import (
    DEFAULT_POLICY,
    merge_policy,
    resolve_policy,
    validate_policy_document,
)


@pytest.fixture
def session_factory(tmp_path):
    db_path = tmp_path / "policy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)

    def _factory():
        return factory()

    return _factory


def test_project_without_override_inherits_global(session_factory):
    db = session_factory()
    db.add(Config(key="governance", value={"ttl_max_age_days": 400}))
    db.add(Project(name="p1"))
    db.commit()
    db.close()

    policy = resolve_policy("p1", session_factory=session_factory)
    assert policy.ttl_max_age_days == 400
    assert policy.ttl_idle_days == DEFAULT_POLICY["ttl_idle_days"]


def test_override_partial_merge(session_factory):
    db = session_factory()
    db.add(Config(key="governance", value={"ttl_max_age_days": 400, "ttl_idle_days": 80}))
    db.add(Project(name="p1"))
    db.add(GovernancePolicy(project_name="p1", overrides={"ttl_idle_days": 120}))
    db.commit()
    db.close()

    policy = resolve_policy("p1", session_factory=session_factory)
    assert policy.ttl_max_age_days == 400
    assert policy.ttl_idle_days == 120


def test_missing_global_fields_use_defaults():
    doc = validate_policy_document({})
    assert doc["quarantine_window_days"] == DEFAULT_POLICY["quarantine_window_days"]


def test_invalid_similarity_threshold():
    with pytest.raises(ValidationError):
        validate_policy_document({"similarity_threshold": 1.5})


def test_invalid_tiebreak():
    with pytest.raises(ValidationError):
        validate_policy_document({"contradiction_tiebreak": "votes"})


def test_merge_policy_deterministic():
    merged = merge_policy({"ttl_max_age_days": 100}, {"ttl_idle_days": 10})
    assert merged["ttl_max_age_days"] == 100
    assert merged["ttl_idle_days"] == 10


# ---------------------------------------------------------------------------
# max_memories / cold_tier policy fields (task_05 / ADR-005)
# ---------------------------------------------------------------------------

def test_default_policy_quota_fields():
    doc = validate_policy_document({})
    assert doc["max_memories"] is None
    assert doc["max_memories_action"] == "alert"
    assert doc["cold_tier_idle_days"] == 180


def test_invalid_max_memories_action_rejected():
    with pytest.raises(ValidationError):
        validate_policy_document({"max_memories_action": "bogus"})


def test_max_memories_must_be_positive():
    with pytest.raises(ValidationError):
        validate_policy_document({"max_memories": 0})


def test_override_sets_quota_fields():
    merged = merge_policy(
        dict(DEFAULT_POLICY),
        {"max_memories": 1000, "max_memories_action": "enforce", "cold_tier_idle_days": 90},
    )
    assert merged["max_memories"] == 1000
    assert merged["max_memories_action"] == "enforce"
    assert merged["cold_tier_idle_days"] == 90


def test_override_inherits_global_quota_when_absent():
    merged = merge_policy({**DEFAULT_POLICY, "max_memories": 500}, {"ttl_idle_days": 30})
    assert merged["max_memories"] == 500



# ---------------------------------------------------------------------------
# Individual process toggles (processes_enabled)
# ---------------------------------------------------------------------------


def test_default_policy_has_all_processes_enabled():
    doc = validate_policy_document({})
    assert set(doc["processes_enabled"]) == set(
        {
            "dedup",
            "ttl_prune",
            "consolidate",
            "purge",
            "quality_eval",
            "enforce_quota",
            "cold_tier",
            "merge_projects",
        }
    )
    assert doc["processes_enabled"]["consolidate"] is False
    assert all(
        enabled
        for process, enabled in doc["processes_enabled"].items()
        if process != "consolidate"
    )


def test_consolidate_inherits_legacy_consolidation_enabled():
    doc = validate_policy_document({"consolidation_enabled": True})
    assert doc["processes_enabled"]["consolidate"] is True
    doc = validate_policy_document({"consolidation_enabled": False})
    assert doc["processes_enabled"]["consolidate"] is False


def test_invalid_process_key_rejected():
    with pytest.raises(ValidationError):
        validate_policy_document({"processes_enabled": {"bogus": True}})


def test_process_toggle_roundtrip_merge_policy():
    merged = merge_policy(
        {**DEFAULT_POLICY, "processes_enabled": {"purge": False, "dedup": True}},
        {"ttl_idle_days": 30},
    )
    assert merged["processes_enabled"]["purge"] is False
    assert merged["processes_enabled"]["dedup"] is True
    assert merged["processes_enabled"]["merge_projects"] is True


def test_is_process_enabled_helper(session_factory):
    from app.utils.governance_policy import is_process_enabled, resolve_policy

    db = session_factory()
    db.add(Config(key="governance", value={"processes_enabled": {"purge": False}}))
    db.add(Project(name="p1"))
    db.commit()
    db.close()

    policy = resolve_policy("p1", session_factory=session_factory)
    assert is_process_enabled(policy, "purge") is False
    assert is_process_enabled(policy, "dedup") is True
    assert is_process_enabled(policy, "not_a_process") is False


def test_project_override_cannot_change_global_process_toggle():
    global_doc = {
        **DEFAULT_POLICY,
        "processes_enabled": {**DEFAULT_POLICY["processes_enabled"], "purge": False},
    }
    merged = merge_policy(global_doc, {"processes_enabled": {"purge": True}})
    assert merged["processes_enabled"]["purge"] is False
