"""Tests for automatic near-duplicate superseding after a write.

The store accumulates paraphrases of the same fact because extraction is ADD-only
and the LLM only sees neighbours of the whole submission, never of each extracted
fact. These tests pin the safety properties of the fix, which matter more than the
detection itself: it is OFF unless asked for, it can run in report mode without
touching data, and it never fails the write that triggered it.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")


from app.utils import autodedup
from app.utils.autodedup import autodedup_after_write, find_near_duplicates


def _hit(mem_id, score, data="texto", state="active"):
    return SimpleNamespace(
        id=mem_id, score=score, payload={"data": data, "state": state}
    )


def _client(hits):
    client = MagicMock()
    client.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    client.vector_store.search.return_value = hits
    return client


def _result(*pairs):
    return {"results": [{"id": i, "memory": m, "event": "ADD"} for i, m in pairs]}


class TestMode:
    def test_off_by_default(self, monkeypatch):
        """Changing stored data must be opt-in."""
        monkeypatch.delenv("MEM0_AUTODEDUP_MODE", raising=False)
        client = _client([_hit("dup", 0.99)])

        out = autodedup_after_write(client, _result(("new", "um fato")))

        assert out["mode"] == "off"
        assert out["candidates"] == []
        client.vector_store.search.assert_not_called()

    def test_report_mode_detects_without_touching_data(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_MODE", "report")
        client = _client([_hit("dup", 0.99)])

        with patch("app.utils.supersedes.mark_points_obsolete") as mark:
            out = autodedup_after_write(client, _result(("new", "um fato")))

        assert [c["duplicate_id"] for c in out["candidates"]] == ["dup"]
        assert "superseded" not in out
        mark.assert_not_called()

    def test_apply_mode_supersedes(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_MODE", "apply")
        client = _client([_hit("dup", 0.99)])

        with patch(
            "app.utils.supersedes.mark_points_obsolete",
            return_value={"updated": ["dup"], "missing": []},
        ) as mark:
            out = autodedup_after_write(client, _result(("new", "um fato")))

        assert out["superseded"] == ["dup"]
        assert mark.call_args.kwargs["superseded_by"] == "new"

    def test_unknown_mode_falls_back_to_off(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_MODE", "seila")
        assert autodedup.autodedup_mode() == "off"


class TestDetection:
    def test_below_threshold_is_not_a_duplicate(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_THRESHOLD", "0.95")
        client = _client([_hit("parecida", 0.90)])

        assert find_near_duplicates(client, [{"id": "new", "memory": "x"}]) == []

    def test_ignores_memories_written_by_the_same_job(self, monkeypatch):
        """A submission that states a fact twice must not supersede itself."""
        monkeypatch.setenv("MEM0_AUTODEDUP_THRESHOLD", "0.90")
        client = _client([_hit("irmao", 0.99), _hit("antiga", 0.98)])

        found = find_near_duplicates(
            client,
            [{"id": "irmao", "memory": "a"}, {"id": "novo", "memory": "b"}],
        )

        assert {c["duplicate_id"] for c in found} == {"antiga"}

    def test_ignores_already_obsolete_points(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_THRESHOLD", "0.90")
        client = _client([_hit("velha", 0.99, state="obsolete")])

        assert find_near_duplicates(client, [{"id": "new", "memory": "x"}]) == []

    def test_lookup_failure_does_not_raise(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_THRESHOLD", "0.90")
        client = _client([])
        client.vector_store.search.side_effect = RuntimeError("qdrant fora")

        assert find_near_duplicates(client, [{"id": "new", "memory": "x"}]) == []

    def test_deleted_events_are_not_candidates(self, monkeypatch):
        monkeypatch.setenv("MEM0_AUTODEDUP_MODE", "report")
        client = _client([_hit("dup", 0.99)])

        out = autodedup_after_write(
            client, {"results": [{"id": "x", "memory": "m", "event": "DELETE"}]}
        )

        assert out["candidates"] == []
        client.vector_store.search.assert_not_called()
