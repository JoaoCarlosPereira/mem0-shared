"""Tests para o worker de backup dedicado (task_05 / ADR-002).

Exercita a decisão de agenda (cadência × último backup × run_at/timezone) e o
tick com relógio e archive mockados — sem infraestrutura nem asyncio real além
de ``asyncio.run`` para o tick.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.schemas import BackupArchiveInfo, BackupPolicySchema
from app.workers.backup_worker import BackupWorker


class FakeArchive:
    def __init__(self, policy, archives=None, fail=False):
        self._policy = policy
        self._archives = archives or []
        self._fail = fail
        self.created = 0

    @property
    def policy(self):
        return self._policy

    def list(self):
        return list(self._archives)

    def create(self, *, tag=None):
        if self._fail:
            raise RuntimeError("create boom")
        self.created += 1
        return type("R", (), {"name": "20260618-030000.zip"})()


def _info(name, dt):
    return BackupArchiveInfo(name=name, created_at=dt, size=1, location="local")


def _worker(archive, now):
    return BackupWorker(lambda: archive, clock=lambda: now)


def _policy(**kw):
    base = dict(enabled=True, frequency="daily", run_at="03:00", timezone="UTC", local_dir="/x")
    base.update(kw)
    return BackupPolicySchema(**base)


# -- due() ------------------------------------------------------------------
def test_disabled_is_never_due():
    arc = FakeArchive(_policy(enabled=False))
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    assert _worker(arc, now).due(arc) is False


def test_daily_due_when_no_backup_after_run_at():
    arc = FakeArchive(_policy())
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)  # após 03:00
    assert _worker(arc, now).due(arc) is True


def test_not_due_before_run_at():
    arc = FakeArchive(_policy())
    now = datetime(2026, 6, 18, 2, 0, tzinfo=UTC)  # antes de 03:00
    assert _worker(arc, now).due(arc) is False


def test_daily_not_due_when_already_backed_up_in_period():
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    arc = FakeArchive(_policy(), archives=[_info("20260618-030500.zip", datetime(2026, 6, 18, 3, 5, tzinfo=UTC))])
    assert _worker(arc, now).due(arc) is False  # backup feito há ~55min


def test_daily_due_after_24h():
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    arc = FakeArchive(_policy(), archives=[_info("20260617-030000.zip", datetime(2026, 6, 17, 3, 0, tzinfo=UTC))])
    assert _worker(arc, now).due(arc) is True  # 25h depois


def test_weekly_not_due_after_3_days():
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    arc = FakeArchive(
        _policy(frequency="weekly"),
        archives=[_info("20260615-030000.zip", datetime(2026, 6, 15, 3, 0, tzinfo=UTC))],
    )
    assert _worker(arc, now).due(arc) is False


def test_weekly_due_after_8_days():
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    arc = FakeArchive(
        _policy(frequency="weekly"),
        archives=[_info("20260610-030000.zip", datetime(2026, 6, 10, 3, 0, tzinfo=UTC))],
    )
    assert _worker(arc, now).due(arc) is True


def test_pre_restore_archive_does_not_count_as_backup():
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    # só há um pre-restore hoje; mesmo assim o backup regular é devido
    arc = FakeArchive(
        _policy(),
        archives=[_info("pre-restore-20260618-031000.zip", datetime(2026, 6, 18, 3, 10, tzinfo=UTC))],
    )
    assert _worker(arc, now).due(arc) is True


# -- tick() -----------------------------------------------------------------
def test_tick_creates_when_due():
    arc = FakeArchive(_policy())
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    ran = asyncio.run(_worker(arc, now).tick())
    assert ran is True
    assert arc.created == 1


def test_tick_skips_when_not_due():
    arc = FakeArchive(_policy(enabled=False))
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    ran = asyncio.run(_worker(arc, now).tick())
    assert ran is False
    assert arc.created == 0


def test_tick_swallows_create_failure():
    arc = FakeArchive(_policy(), fail=True)
    now = datetime(2026, 6, 18, 4, 0, tzinfo=UTC)
    ran = asyncio.run(_worker(arc, now).tick())  # não deve levantar
    assert ran is False
