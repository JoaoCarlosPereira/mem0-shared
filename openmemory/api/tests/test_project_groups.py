"""Tests for project families (MEM0_PROJECT_GROUPS).

``project`` comes from the session's working directory, but one task crosses
repositories, so the same subject lands under ``sysmovs``, ``sysmos1-modular``
and ``db-sysmo-s1``. Grouping them makes the ranking hint reward the subject
instead of whichever directory the agent was rooted at, and makes
``strict_project`` mean the family rather than one repo.

Global (non-strict) reads must stay global — that is asserted here too, because
it is the property most easily broken by a change in this area.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app import mcp_server
from app.mcp_server import search_memory
from app.utils import project_groups
from app.utils.project_groups import (
    projects_in_group,
    resolve_project_group,
    same_project_family,
)
from app.utils.recency import SEARCH_PROJECT_BOOST_EXACT, project_match_factor

GROUPS = "sysmo-s1=sysmovs,sysmos1-modular,db-sysmo-s1"


@pytest.fixture(autouse=True)
def _clear_cache():
    project_groups.reset_project_group_cache()
    yield
    project_groups.reset_project_group_cache()


@pytest.fixture
def grouped(monkeypatch):
    monkeypatch.setenv("MEM0_PROJECT_GROUPS", GROUPS)
    project_groups.reset_project_group_cache()


class TestParsing:
    def test_members_and_label_resolve_to_the_group(self, grouped):
        for name in ("sysmovs", "sysmos1-modular", "db-sysmo-s1", "sysmo-s1"):
            assert resolve_project_group(name) == "sysmo-s1"

    def test_unlisted_project_has_no_group(self, grouped):
        assert resolve_project_group("ms-dashboard-s1") is None

    def test_matching_ignores_case_and_punctuation(self, grouped):
        assert resolve_project_group("SysmoS1_Modular") == "sysmo-s1"

    def test_no_config_means_no_groups(self, monkeypatch):
        monkeypatch.delenv("MEM0_PROJECT_GROUPS", raising=False)
        project_groups.reset_project_group_cache()
        assert resolve_project_group("sysmovs") is None
        assert projects_in_group("sysmovs") == []

    def test_malformed_entries_are_skipped(self, monkeypatch):
        monkeypatch.setenv("MEM0_PROJECT_GROUPS", "lixo;=nada;g=a,b")
        project_groups.reset_project_group_cache()
        assert resolve_project_group("a") == "g"
        assert resolve_project_group("lixo") is None

    def test_group_membership_is_symmetric(self, grouped):
        assert same_project_family("sysmovs", "db-sysmo-s1")
        assert not same_project_family("sysmovs", "ms-dashboard-s1")


class TestRankingHint:
    def test_sibling_earns_the_exact_match_boost(self, grouped):
        """Searching from sysmovs must not under-rank the DLL repo's memories."""
        assert project_match_factor("sysmos1-modular", "sysmovs") == pytest.approx(
            1.0 + SEARCH_PROJECT_BOOST_EXACT
        )

    def test_unrelated_project_is_not_boosted(self, grouped):
        assert project_match_factor("ms-dashboard-s1", "sysmovs") == 1.0

    def test_without_groups_sibling_is_not_boosted(self, monkeypatch):
        monkeypatch.delenv("MEM0_PROJECT_GROUPS", raising=False)
        project_groups.reset_project_group_cache()
        assert project_match_factor("sysmos1-modular", "sysmovs") == 1.0


@pytest.fixture
def patched_client():
    client = MagicMock()
    client.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    client.embedding_model.model = "test-embed-model"
    client.vector_store.search.return_value = [
        SimpleNamespace(id="1", score=0.9, payload={"data": "m", "project": "sysmovs"})
    ]
    client.vector_store.collection_name = "openmemory"
    with (
        patch.object(mcp_server, "get_memory_client_safe", return_value=client),
        patch.object(mcp_server, "bind_active_collection"),
        patch.object(mcp_server.read_cache, "get_search", return_value=None),
        patch.object(mcp_server.read_cache, "set_search"),
        patch.object(mcp_server.read_cache, "get_embedding", return_value=None),
        patch.object(mcp_server.read_cache, "set_embedding"),
    ):
        yield client


class TestStrictProjectScope:
    @pytest.mark.asyncio
    async def test_strict_covers_the_whole_family(self, patched_client, grouped):
        await search_memory("q", project="sysmovs", strict_project=True)

        filters = patched_client.vector_store.search.call_args.kwargs["filters"]
        assert set(filters["project"]["in"]) == {
            "sysmo-s1",
            "sysmovs",
            "sysmos1-modular",
            "db-sysmo-s1",
        }

    @pytest.mark.asyncio
    async def test_strict_on_ungrouped_project_stays_exact(
        self, patched_client, grouped
    ):
        await search_memory("q", project="ms-dashboard-s1", strict_project=True)

        filters = patched_client.vector_store.search.call_args.kwargs["filters"]
        assert filters == {"project": "ms-dashboard-s1"}

    @pytest.mark.asyncio
    async def test_default_search_stays_global_even_with_groups(
        self, patched_client, grouped
    ):
        """Grouping must never turn the default read into a filtered one."""
        data = json.loads(await search_memory("q", project="sysmovs"))

        assert patched_client.vector_store.search.call_args.kwargs["filters"] is None
        assert data["results"][0]["project"] == "sysmovs"
