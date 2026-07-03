"""PostgreSQL migration integration tests (task_01).

Skipped unless POSTGRES_TEST_URL is set, e.g.::

    POSTGRES_TEST_URL=postgresql://mem0:mem0@localhost:6432/openmemory pytest tests/test_postgres_migrations.py -v
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_TEST_URL"),
    reason="POSTGRES_TEST_URL not set",
)


@pytest.fixture
def pg_url():
    return os.environ["POSTGRES_TEST_URL"]


def test_alembic_upgrade_head(pg_url, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from alembic import command
    from alembic.config import Config

    ini = tmp_path / "alembic.ini"
    ini.write_text(
        """
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname
""".strip()
    )
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")

    from sqlalchemy import create_engine, inspect

    eng = create_engine(pg_url)
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    # task_01: partitioning state must materialize alongside the existing tables.
    for name in ("write_queue", "projects", "write_audit_logs", "migration_state"):
        assert name in tables
    project_cols = {c["name"] for c in insp.get_columns("projects")}
    assert {"partition_tier", "shard_key"} <= project_cols
    eng.dispose()


def test_write_queue_index_exists(pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from sqlalchemy import create_engine, inspect

    eng = create_engine(pg_url)
    indexes = {idx["name"] for idx in inspect(eng).get_indexes("write_queue")}
    eng.dispose()
    assert "idx_write_queue_status_created" in indexes


def test_groups_migration_creates_table_column_and_default(pg_url, monkeypatch, tmp_path):
    """task_01/ADR-002: groups + users.group_id criados e Default semeado/backfill."""
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from alembic import command
    from alembic.config import Config

    ini = tmp_path / "alembic.ini"
    ini.write_text(
        """
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname
""".strip()
    )
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")

    from sqlalchemy import create_engine, inspect, text

    eng = create_engine(pg_url)
    insp = inspect(eng)
    assert "groups" in set(insp.get_table_names())
    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert "group_id" in user_cols

    with eng.connect() as conn:
        default_count = conn.execute(
            text("SELECT count(*) FROM groups WHERE name = 'Default'")
        ).scalar()
        orphan_users = conn.execute(
            text("SELECT count(*) FROM users WHERE group_id IS NULL")
        ).scalar()
    eng.dispose()

    assert default_count == 1, "deve existir exatamente um grupo Default"
    assert orphan_users == 0, "todos os usuários existentes devem apontar para um grupo"


def test_identity_migration_tables_columns_and_backfill(pg_url, monkeypatch, tmp_path):
    """task_01 auth Google/ADR-004: machines/agent_tokens/link_audit_logs + backfill."""
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from alembic import command
    from alembic.config import Config

    ini = tmp_path / "alembic.ini"
    ini.write_text(
        """
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname
""".strip()
    )
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")

    from sqlalchemy import create_engine, inspect, text

    eng = create_engine(pg_url)
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    for name in ("machines", "agent_tokens", "link_audit_logs"):
        assert name in tables
    user_cols = {c["name"] for c in insp.get_columns("users")}
    assert {"google_sub", "display_name", "avatar_url", "user_type"} <= user_cols

    indexes = {idx["name"] for idx in insp.get_indexes("agent_tokens")}
    assert "uq_agent_tokens_active_user" in indexes, "índice parcial de 1 token ativo"

    with eng.connect() as conn:
        null_types = conn.execute(
            text("SELECT count(*) FROM users WHERE user_type IS NULL")
        ).scalar()
        orphan_machines = conn.execute(
            text(
                "SELECT count(*) FROM users u"
                " LEFT JOIN machines m ON m.hostname = u.user_id"
                " WHERE m.id IS NULL AND u.user_type = 'legacy_host'"
            )
        ).scalar()
    eng.dispose()

    assert null_types == 0, "user_type deve estar preenchido em todas as linhas"
    assert orphan_machines == 0, "todo usuário legado deve ter linha em machines"
