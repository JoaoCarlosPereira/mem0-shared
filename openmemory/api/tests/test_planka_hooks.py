"""Tests for PLANKA_MIRROR_SYNC hooks (task_04)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.database import Base  # noqa: F401
from app.utils import planka_hooks
from app.utils.planka import PlankaMirrorError


def test_mirror_disabled_is_noop(monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "0")
    db = MagicMock()
    with patch("app.utils.planka_hooks.PlankaMirrorHttpClient") as cls:
        planka_hooks.mirror_task(db, uuid4())
        cls.assert_not_called()


def test_mirror_enabled_calls_client(monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    db = MagicMock()
    client = MagicMock()
    client.mirror_task = AsyncMock()
    with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
        planka_hooks.mirror_task(db, uuid4())
    client.mirror_task.assert_awaited()


def test_mirror_failure_raises_http_502(monkeypatch):
    monkeypatch.setenv("PLANKA_MIRROR_SYNC", "1")
    db = MagicMock()
    client = MagicMock()
    client.mirror_task = AsyncMock(side_effect=PlankaMirrorError(503, "down"))
    with patch("app.utils.planka_hooks.PlankaMirrorHttpClient", return_value=client):
        with pytest.raises(HTTPException) as exc:
            planka_hooks.mirror_task(db, uuid4())
    assert exc.value.status_code == 502
    assert exc.value.detail["mirror_failed"] is True
