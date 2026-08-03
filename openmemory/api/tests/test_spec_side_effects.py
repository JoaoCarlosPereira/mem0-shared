"""Tests for fire-and-forget Spec document post-write side effects."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import DocumentType, Project, SpecDocument, SpecWorkspace
from app.utils import spec_side_effects


@pytest.fixture
def factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _mk_doc(db, content: str = "# PRD"):
    if not db.query(Project).filter(Project.name == "mem0-shared").first():
        db.add(Project(name="mem0-shared"))
        db.commit()
    ws = SpecWorkspace(project_id="mem0-shared", slug=f"ws-{uuid4().hex[:8]}", name="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    doc = SpecDocument(
        workspace_id=ws.id,
        document_type=DocumentType.prd,
        current_content=content,
        current_version=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return ws, doc


def test_schedule_runs_index_in_background(factory, monkeypatch):
    monkeypatch.setattr(spec_side_effects, "SessionLocal", factory)

    db = factory()
    ws, _doc = _mk_doc(db)
    ws_id = ws.id
    db.close()

    done = threading.Event()
    calls: list = []

    def fake_index(session, workspace, document, **kwargs):
        calls.append(workspace.id)
        done.set()
        return True

    with patch("app.utils.spec_search.index_document_now", side_effect=fake_index):
        with patch("app.utils.planka_hooks.mirror_document_best_effort") as mirror:
            spec_side_effects.schedule_document_post_write(
                ws_id, DocumentType.prd.value, mirror=True
            )
            assert done.wait(timeout=2.0), "background index never ran"
            time.sleep(0.05)
            mirror.assert_called_once()

    assert calls == [ws_id]


def test_schedule_without_mirror_skips_planka(factory, monkeypatch):
    monkeypatch.setattr(spec_side_effects, "SessionLocal", factory)
    db = factory()
    ws, _doc = _mk_doc(db)
    ws_id = ws.id
    db.close()

    done = threading.Event()

    def fake_index(*_a, **_k):
        done.set()
        return True

    with patch("app.utils.spec_search.index_document_now", side_effect=fake_index):
        with patch("app.utils.planka_hooks.mirror_document_best_effort") as mirror:
            spec_side_effects.schedule_document_post_write(
                ws_id, DocumentType.prd.value, mirror=False
            )
            assert done.wait(timeout=2.0)
            time.sleep(0.05)
            mirror.assert_not_called()
