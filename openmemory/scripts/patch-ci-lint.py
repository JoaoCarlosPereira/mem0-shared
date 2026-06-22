#!/usr/bin/env python3
"""Apply CI lint fixes to root-owned openmemory/api files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "api"


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            print(f"skip (already ok): {path.name}")
            return
        raise SystemExit(f"pattern not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path}")


def main() -> None:
    _replace(
        ROOT / "app/routers/admin.py",
        "from datetime import datetime, timedelta\n",
        "from datetime import datetime\n",
    )
    _replace(
        ROOT / "app/routers/admin.py",
        "    GovernanceJobStatus,\n    Memory,\n    MemoryState,\n    Project,\n",
        "    GovernanceJobStatus,\n    Project,\n",
    )
    _replace(
        ROOT / "app/routers/governance_project_merge.py",
        "from fastapi import APIRouter, Depends, HTTPException, Query\n",
        "from fastapi import APIRouter, HTTPException, Query\n",
    )
    _replace(
        ROOT / "app/routers/governance_schedule.py",
        "from typing import List\n\n",
        "",
    )
    gs = ROOT / "app/routers/governance_schedule.py"
    text = gs.read_text(encoding="utf-8").replace("List[int]", "list[int]")
    gs.write_text(text, encoding="utf-8")
    print(f"patched {gs}")

    _replace(
        ROOT / "tests/test_config_save.py",
        "from app.models import Base, Config as ConfigModel\nfrom app.utils import memory as memory_mod\n",
        "from app.models import Base\n",
    )
    _replace(
        ROOT / "tests/test_governance_schedule.py",
        "from zoneinfo import ZoneInfo\n\n",
        "",
    )
    _replace(
        ROOT / "tests/test_vector_stats.py",
        "from datetime import UTC, datetime, timedelta\n",
        "from datetime import UTC, datetime\n",
    )
    _replace(
        ROOT / "tests/test_vector_stats.py",
        "import pytest\n\nfrom app.utils import vector_stats\n",
        "from app.utils import vector_stats\n",
    )

    # Rewrite isolated-import test to use package import (Pydantic + future annotations).
    api_test = ROOT / "tests/test_governance_schedule_api.py"
    api_test.write_text(
        '''"""Tests for governance schedule API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import Base, Config
from app.routers.governance_schedule import router


@pytest.fixture
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'sched.db'}")
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def make_client(factory):
    app = FastAPI()
    app.include_router(router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def test_get_schedule_defaults(factory):
    client = make_client(factory)
    resp = client.get("/admin/governance/schedule")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schedule_timezone"] == "UTC"
    assert body["schedule_start_time"] == "02:00"
    assert 0 in body["schedule_weekdays"]


def test_put_schedule_persists(factory):
    client = make_client(factory)
    payload = {
        "schedule_timezone": "America/Sao_Paulo",
        "schedule_weekdays": [5, 6],
        "schedule_start_time": "01:30",
        "schedule_end_time": "04:45",
    }
    resp = client.put("/admin/governance/schedule", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["schedule_timezone"] == "America/Sao_Paulo"
    assert body["schedule_weekdays"] == [5, 6]

    db = factory()
    row = db.query(Config).filter(Config.key == "governance").one()
    db.close()
    assert row.value["schedule_start_time"] == "01:30"
''',
        encoding="utf-8",
    )
    print(f"rewrote {api_test}")


if __name__ == "__main__":
    main()
