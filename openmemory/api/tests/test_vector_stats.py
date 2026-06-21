"""Regression tests for Qdrant-backed vector_stats helpers (UI/admin fix)."""

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app.utils import vector_stats


def _point(mem_id, data, project, created_at=None):
    created = created_at or datetime.now(UTC).isoformat()
    return SimpleNamespace(
        id=mem_id,
        payload={
            "data": data,
            "project": project,
            "created_at": created,
        },
    )


def _make_vs(*, count_total=0, count_by_project=None, scroll_batches=None):
    vs = MagicMock()
    vs.collection_name = "openmemory"
    vs.client.count.return_value = SimpleNamespace(count=count_total)
    vs._create_filter.return_value = MagicMock()

    if count_by_project is not None:
        def _count(**kwargs):
            filt = kwargs.get("count_filter")
            _ = filt
            return SimpleNamespace(count=count_by_project)

        vs.client.count.side_effect = _count

    if scroll_batches is not None:
        vs.client.scroll.side_effect = scroll_batches
    else:
        vs.client.scroll.return_value = ([], None)

    client = MagicMock()
    client.vector_store = vs
    client.embedding_model.embed.return_value = [0.1, 0.2]
    return client, vs


class TestCountHelpers:
    def test_count_collection_memories_returns_zero_when_client_unavailable(self):
        with patch.object(vector_stats, "_vector_store", return_value=(None, None)):
            assert vector_stats.count_collection_memories() == 0

    def test_count_collection_memories_reads_qdrant_count(self):
        client, vs = _make_vs(count_total=525)
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            assert vector_stats.count_collection_memories() == 525
        vs.client.count.assert_called_once_with(
            collection_name="openmemory",
            exact=True,
        )

    def test_count_project_memories_uses_project_filter(self):
        client, vs = _make_vs(count_by_project=42)
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            assert vector_stats.count_project_memories("sysmovs") == 42
        vs._create_filter.assert_called_once_with({"project": "sysmovs"})

    def test_count_memories_last_24h_counts_recent_payloads_only(self):
        recent = datetime.now(UTC).isoformat()
        old = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        client, vs = _make_vs(
            scroll_batches=[
                ([_point("1", "a", "p", recent), _point("2", "b", "p", old)], None),
            ]
        )
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            assert vector_stats.count_memories_last_24h() == 1


class TestListSharedMemories:
    def test_list_shared_memories_empty_when_client_unavailable(self):
        with patch.object(vector_stats, "_vector_store", return_value=(None, None)):
            out = vector_stats.list_shared_memories(page=1, size=10)
        assert out == {"items": [], "total": 0, "page": 1, "size": 10, "pages": 0}

    def test_list_shared_memories_paginates_scroll_results(self):
        points = [
            _point("a", "first", "sysmovs", "2026-06-21T10:00:00+00:00"),
            _point("b", "second", "sysmovs", "2026-06-20T10:00:00+00:00"),
            _point("c", "third", "sysmovs", "2026-06-19T10:00:00+00:00"),
        ]
        client, vs = _make_vs()
        vs.client.scroll.return_value = (points, None)
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            page1 = vector_stats.list_shared_memories(page=1, size=2)
            page2 = vector_stats.list_shared_memories(page=2, size=2)

        assert page1["total"] == 3
        assert page1["pages"] == 2
        assert len(page1["items"]) == 2
        assert page1["items"][0]["content"] == "first"
        assert page1["items"][0]["app_name"] == "sysmovs"
        assert page2["items"][0]["content"] == "third"

    def test_list_shared_memories_search_uses_vector_search(self):
        hit = SimpleNamespace(
            id="x",
            score=0.9,
            payload={"data": "match", "project": "sysmovs", "created_at": "2026-06-21T00:00:00+00:00"},
        )
        client, vs = _make_vs()
        client.vector_store.search.return_value = [hit]
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            with patch("app.utils.partitioning.resolve_and_bind", return_value=SimpleNamespace(shard_key=None)):
                out = vector_stats.list_shared_memories(search="match", page=1, size=10)

        assert out["total"] == 1
        assert out["items"][0]["content"] == "match"
        client.vector_store.search.assert_called_once()


class TestGetSharedMemoryById:
    def test_returns_none_when_client_unavailable(self):
        with patch.object(vector_stats, "_vector_store", return_value=(None, None)):
            assert vector_stats.get_shared_memory_by_id("abc") is None

    def test_returns_memory_payload_when_found(self):
        mem_id = "a6a0dc5b-ebff-4156-add4-48c09f7ffa8a"
        point = _point(mem_id, "hello world", "sysmovs", "2026-06-21T06:35:17.834714+00:00")
        client, vs = _make_vs()
        vs.client.retrieve.return_value = [point]
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            out = vector_stats.get_shared_memory_by_id(mem_id)

        assert out is not None
        assert out["id"] == mem_id
        assert out["text"] == "hello world"
        assert out["app_name"] == "sysmovs"
        assert out["state"] == "active"
        vs.client.retrieve.assert_called_once_with(
            collection_name="openmemory",
            ids=[mem_id],
            with_payload=True,
            with_vectors=False,
        )

    def test_returns_none_when_not_found(self):
        client, vs = _make_vs()
        vs.client.retrieve.return_value = []
        with patch.object(vector_stats, "_vector_store", return_value=(client, vs)):
            assert vector_stats.get_shared_memory_by_id("missing") is None
