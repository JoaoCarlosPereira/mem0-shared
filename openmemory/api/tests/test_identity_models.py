"""Testes da task_01 (feature auth Google): modelos e migração de identidade.

Unitários rodam em SQLite em memória (padrão do repo). A migração Alembic é
exercitada de verdade em um SQLite de arquivo temporário (a cadeia inteira é
dialect-aware), cobrindo criação das tabelas, backfill e downgrade sem depender
de PostgreSQL — os asserts específicos de PG vivem em
``test_postgres_migrations.py``.
"""

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    USER_TYPE_LEGACY_HOST,
    USER_TYPE_PERSON,
    AgentToken,
    LinkAuditLog,
    Machine,
    MachineStatus,
    User,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _mk_user(db, user_id: str, **kwargs) -> User:
    user = User(user_id=user_id, **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestMachineModel:
    def test_hostname_unico_persiste_e_recupera(self, db_session):
        machine = Machine(hostname="DESKTOP-01")
        db_session.add(machine)
        db_session.commit()

        found = db_session.query(Machine).filter_by(hostname="DESKTOP-01").one()
        assert found.status == MachineStatus.unlinked
        assert found.linked_user_id is None

    def test_hostname_duplicado_viola_unicidade(self, db_session):
        db_session.add(Machine(hostname="DESKTOP-01"))
        db_session.commit()
        db_session.add(Machine(hostname="DESKTOP-01"))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_vinculo_navega_para_pessoa_e_legado(self, db_session):
        person = _mk_user(
            db_session, "google-sub-1",
            user_type=USER_TYPE_PERSON, google_sub="google-sub-1",
        )
        legacy = _mk_user(db_session, "DESKTOP-01")
        machine = Machine(
            hostname="DESKTOP-01",
            linked_user_id=person.id,
            legacy_user_id=legacy.id,
            status=MachineStatus.linked,
        )
        db_session.add(machine)
        db_session.commit()

        db_session.refresh(machine)
        assert machine.linked_user.google_sub == "google-sub-1"
        assert machine.legacy_user.user_id == "DESKTOP-01"


class TestAgentTokenModel:
    def test_persiste_somente_hash_e_prefixo(self, db_session):
        user = _mk_user(db_session, "sub-1", user_type=USER_TYPE_PERSON)
        token = AgentToken(user_id=user.id, token_hash="a" * 64, prefix="omtk_2F9K")
        db_session.add(token)
        db_session.commit()

        cols = {c.name for c in AgentToken.__table__.columns}
        assert "token_hash" in cols and "prefix" in cols
        assert not any("plain" in c or c == "token" for c in cols)

    def test_segundo_token_ativo_para_mesmo_usuario_rejeitado(self, db_session):
        user = _mk_user(db_session, "sub-1", user_type=USER_TYPE_PERSON)
        db_session.add(AgentToken(user_id=user.id, token_hash="a" * 64, prefix="omtk_a"))
        db_session.commit()
        db_session.add(AgentToken(user_id=user.id, token_hash="b" * 64, prefix="omtk_b"))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_token_revogado_libera_novo_ativo(self, db_session):
        user = _mk_user(db_session, "sub-1", user_type=USER_TYPE_PERSON)
        old = AgentToken(user_id=user.id, token_hash="a" * 64, prefix="omtk_a")
        db_session.add(old)
        db_session.commit()

        from app.models import get_current_utc_time
        old.revoked_at = get_current_utc_time()
        db_session.add(AgentToken(user_id=user.id, token_hash="b" * 64, prefix="omtk_b"))
        db_session.commit()

        active = (
            db_session.query(AgentToken)
            .filter(AgentToken.user_id == user.id, AgentToken.revoked_at.is_(None))
            .all()
        )
        assert len(active) == 1
        assert active[0].prefix == "omtk_b"


class TestUserIdentityColumns:
    def test_google_sub_aceita_null_em_multiplas_linhas(self, db_session):
        _mk_user(db_session, "DESKTOP-01")
        _mk_user(db_session, "DESKTOP-02")
        legacy_rows = db_session.query(User).filter(User.google_sub.is_(None)).count()
        assert legacy_rows == 2

    def test_google_sub_duplicado_rejeitado(self, db_session):
        _mk_user(db_session, "sub-1", google_sub="dup", user_type=USER_TYPE_PERSON)
        db_session.add(User(user_id="sub-2", google_sub="dup", user_type=USER_TYPE_PERSON))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_type_default_legacy_host(self, db_session):
        user = _mk_user(db_session, "DESKTOP-01")
        assert user.user_type == USER_TYPE_LEGACY_HOST


class TestLinkAuditLog:
    def test_grava_json_e_navega_relacoes(self, db_session):
        person = _mk_user(db_session, "sub-1", user_type=USER_TYPE_PERSON)
        machine = Machine(hostname="DESKTOP-01")
        db_session.add(machine)
        db_session.commit()

        log = LinkAuditLog(
            machine_id=machine.id,
            actor_user_id=person.id,
            action="link",
            detail={"memories_count": 42},
        )
        db_session.add(log)
        db_session.commit()

        found = db_session.query(LinkAuditLog).one()
        assert found.detail == {"memories_count": 42}
        assert found.machine.hostname == "DESKTOP-01"
        assert found.actor.id == person.id


class TestIdentityMigrationSqlite:
    """Exercita a migração real (upgrade/backfill/downgrade) em SQLite."""

    @pytest.fixture
    def alembic_cfg(self, tmp_path, monkeypatch):
        from alembic.config import Config

        db_path = tmp_path / "identity.db"
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
        ini = tmp_path / "alembic.ini"
        ini.write_text(
            "[alembic]\n"
            "script_location = alembic\n"
            "sqlalchemy.url = driver://user:pass@localhost/dbname\n"
            "\n"
            "[loggers]\nkeys = root\n\n"
            "[handlers]\nkeys = console\n\n"
            "[formatters]\nkeys = generic\n\n"
            "[logger_root]\nlevel = WARN\nhandlers = console\n\n"
            "[handler_console]\nclass = StreamHandler\n"
            "args = (sys.stderr,)\nlevel = NOTSET\nformatter = generic\n\n"
            "[formatter_generic]\nformat = %(levelname)s %(message)s\n"
        )
        cfg = Config(str(ini))
        cfg.set_main_option(
            "script_location",
            str(Path(__file__).resolve().parents[1] / "alembic"),
        )
        return cfg, f"sqlite:///{db_path}"

    def test_upgrade_cria_tabelas_faz_backfill_e_downgrade_remove(self, alembic_cfg):
        from alembic import command

        cfg, url = alembic_cfg
        # Sobe até o head anterior e semeia usuários legados (pré-feature).
        command.upgrade(cfg, "f1a2b3c4d5e6")
        eng = create_engine(url)
        with eng.begin() as conn:
            for host in ("DESKTOP-01", "DESKTOP-02"):
                conn.execute(
                    sa.text(
                        "INSERT INTO users (id, user_id, created_at, updated_at)"
                        " VALUES (:id, :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"id": str(uuid.uuid4()), "uid": host},
                )

        # Upgrade da feature: tabelas + colunas + backfill.
        command.upgrade(cfg, "head")
        insp = sa.inspect(eng)
        tables = set(insp.get_table_names())
        assert {"machines", "agent_tokens", "link_audit_logs"} <= tables
        user_cols = {c["name"] for c in insp.get_columns("users")}
        assert {"google_sub", "display_name", "avatar_url", "user_type"} <= user_cols

        with eng.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT hostname, status, legacy_user_id FROM machines ORDER BY hostname"
                )
            ).fetchall()
            legacy_types = conn.execute(
                sa.text("SELECT count(*) FROM users WHERE user_type = 'legacy_host'")
            ).scalar()
        assert [r[0] for r in rows] == ["DESKTOP-01", "DESKTOP-02"]
        assert all(r[1] == "unlinked" and r[2] is not None for r in rows)
        assert legacy_types == 2

        # Idempotência: reexecutar o upgrade não duplica nada.
        command.downgrade(cfg, "f1a2b3c4d5e6")
        command.upgrade(cfg, "head")
        with eng.connect() as conn:
            machine_count = conn.execute(sa.text("SELECT count(*) FROM machines")).scalar()
        assert machine_count == 2

        # Downgrade (abaixo da feature inteira) remove tabelas e colunas.
        command.downgrade(cfg, "f1a2b3c4d5e6")
        insp = sa.inspect(eng)
        tables = set(insp.get_table_names())
        assert not ({"machines", "agent_tokens", "link_audit_logs"} & tables)
        user_cols = {c["name"] for c in insp.get_columns("users")}
        assert not ({"google_sub", "user_type"} & user_cols)
        eng.dispose()
