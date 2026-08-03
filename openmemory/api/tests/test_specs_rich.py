"""REST additive — labels, checklists, attachments, due_at/position (task_05)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.routers.specs import router as specs_router
from app.routers.specs_rich import router as specs_rich_router


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


@pytest.fixture
def client(factory, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    monkeypatch.setenv("SPEC_ATTACHMENTS_DIR", str(tmp_path / "attachments"))

    app = FastAPI()
    app.include_router(specs_router)
    app.include_router(specs_rich_router)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def _ws_and_task(client):
    ws = client.post(
        "/api/v1/specs/workspaces",
        json={"project_id": "mem0-shared", "slug": f"rich-{uuid.uuid4().hex[:8]}", "name": "Rich"},
    ).json()
    task = client.post(
        "/api/v1/specs/tasks",
        json={"workspace_id": ws["id"], "title": "Card rico"},
    ).json()
    return ws, task


class TestLabels:
    def test_crud_label_e_associacao(self, client):
        ws, task = _ws_and_task(client)
        created = client.post(
            f"/api/v1/specs/workspaces/{ws['id']}/labels",
            json={"name": "bug", "color": "#f00"},
        )
        assert created.status_code == 201
        label_id = created.json()["id"]

        listed = client.get(f"/api/v1/specs/workspaces/{ws['id']}/labels")
        assert listed.status_code == 200
        assert any(label["name"] == "bug" for label in listed.json())

        attach = client.post(f"/api/v1/specs/tasks/{task['id']}/labels/{label_id}")
        assert attach.status_code == 200
        assert label_id in [str(x) for x in attach.json().get("label_ids", [])] or any(
            str(label["id"]) == label_id for label in attach.json().get("labels", [])
        )

        task_labels = client.get(f"/api/v1/specs/tasks/{task['id']}/labels")
        assert task_labels.status_code == 200
        assert any(label["id"] == label_id for label in task_labels.json())

        board = client.get(f"/api/v1/specs/workspaces/{ws['id']}")
        assert board.status_code == 200
        card = next(t for t in board.json()["tasks"] if t["id"] == task["id"])
        assert any(label["id"] == label_id for label in card.get("labels", []))

        detach = client.delete(f"/api/v1/specs/tasks/{task['id']}/labels/{label_id}")
        assert detach.status_code == 204
        assert client.get(f"/api/v1/specs/tasks/{task['id']}/labels").json() == []


class TestChecklists:
    def test_checklist_item_toggle(self, client):
        _, task = _ws_and_task(client)
        cl = client.post(
            f"/api/v1/specs/tasks/{task['id']}/checklists",
            json={"title": "QA"},
        )
        assert cl.status_code == 201
        checklist_id = cl.json()["id"]

        item = client.post(
            f"/api/v1/specs/checklists/{checklist_id}/items",
            json={"title": "rodar pytest"},
        )
        assert item.status_code == 201
        item_id = item.json()["id"]
        assert item.json()["is_completed"] is False

        patched = client.patch(
            f"/api/v1/specs/checklists/{checklist_id}/items/{item_id}",
            json={"is_completed": True},
        )
        assert patched.status_code == 200
        assert patched.json()["is_completed"] is True

        listed = client.get(f"/api/v1/specs/tasks/{task['id']}/checklists")
        assert listed.status_code == 200
        assert listed.json()[0]["items"][0]["is_completed"] is True


class TestAttachments:
    def test_upload_download_delete(self, client, tmp_path: Path):
        _, task = _ws_and_task(client)
        content = b"hello-spec-attachment"
        up = client.post(
            f"/api/v1/specs/tasks/{task['id']}/attachments",
            files={"file": ("note.txt", content, "text/plain")},
        )
        assert up.status_code == 201
        body = up.json()
        assert body["filename"] == "note.txt"
        assert body["size_bytes"] == len(content)

        listed = client.get(f"/api/v1/specs/tasks/{task['id']}/attachments")
        assert listed.status_code == 200
        assert any(a["id"] == body["id"] for a in listed.json())

        down = client.get(f"/api/v1/specs/attachments/{body['id']}")
        assert down.status_code == 200
        assert down.content == content

        deleted = client.delete(f"/api/v1/specs/attachments/{body['id']}")
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/specs/attachments/{body['id']}").status_code == 404
        assert client.get(f"/api/v1/specs/tasks/{task['id']}/attachments").json() == []


class TestDueAndPosition:
    def test_patch_due_at_position_com_occ(self, client):
        _, task = _ws_and_task(client)
        due = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc).isoformat()
        r = client.patch(
            f"/api/v1/specs/tasks/{task['id']}",
            json={
                "expected_version": task["version"],
                "due_at": due,
                "position": 100.0,
                "members": ["alice", "bob"],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["position"] == 100.0
        assert body["due_at"] is not None
        assert body["members"] == ["alice", "bob"]
        assert body["version"] == task["version"] + 1

        conflict = client.patch(
            f"/api/v1/specs/tasks/{task['id']}",
            json={"expected_version": task["version"], "position": 200.0},
        )
        assert conflict.status_code == 409
