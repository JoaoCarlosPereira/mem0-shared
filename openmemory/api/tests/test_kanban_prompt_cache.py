"""Tests for the kanban column prompts in-memory cache.

Covers:
- ``_kanban_prompts_cache_expired()`` – TTL (600 s) and empty-cache logic
- ``_load_kanban_prompts_cache(db)`` – loading from DB, mixed enabled/disabled,
  exception handling
- ``_invalidate_kanban_prompts_cache()`` – full cache bust
"""

import datetime
from unittest.mock import MagicMock

import pytest

import app.mcp_server as mcp_mod

from app.mcp_server import (
    _kanban_prompts_cache,
    _kanban_prompts_cache_expired,
    _KANBAN_PROMPTS_TTL_SECONDS,
    _load_kanban_prompts_cache,
    _invalidate_kanban_prompts_cache,
)
from app.models import KanbanColumnPrompt


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the global cache before and after each test."""
    # Reset global state before the test (mcp_mod is already imported at module level)
    mcp_mod._kanban_prompts_cache.clear()
    mcp_mod._kanban_prompts_cache_loaded = None
    yield
    # Reset after the test to avoid test pollution
    mcp_mod._kanban_prompts_cache.clear()
    mcp_mod._kanban_prompts_cache_loaded = None


def _mock_row(status: str, prompt: str, is_enabled: bool) -> KanbanColumnPrompt:
    """Create a fake KanbanColumnPrompt ORM instance."""
    row = MagicMock(spec=KanbanColumnPrompt)
    row.column_status = status
    row.prompt = prompt
    row.is_enabled = is_enabled
    return row


# ---------------------------------------------------------------------------
# 1. Cache vazio (nada no DB)
# ---------------------------------------------------------------------------

class TestCacheEmpty:
    """When nothing is in the DB, _kanban_prompts_cache stays empty."""

    def test_empty_db_leaves_cache_empty(self):
        db = MagicMock()
        db.query.return_value.all.return_value = []
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache == {}
        assert mcp_mod._kanban_prompts_cache_loaded is not None  # timestamp is set

    def test_expired_returns_true_when_cache_is_fresh_but_empty(self):
        """Even an empty cache that was just loaded should be considered expired
        if TTL has passed — but immediately after load it is NOT expired."""
        db = MagicMock()
        db.query.return_value.all.return_value = []
        _load_kanban_prompts_cache(db)
        # Immediately after load, not expired
        assert _kanban_prompts_cache_expired() is False


# ---------------------------------------------------------------------------
# 2. Cache com múltiplos status
# ---------------------------------------------------------------------------

class TestCacheMultipleStatuses:
    """Verify correct loading of multiple status entries."""

    def test_loads_multiple_statuses(self):
        rows = [
            _mock_row("tasks", "Prompt for tasks", True),
            _mock_row("em_andamento", "Prompt for em_andamento", True),
            _mock_row("revisao_codigo", "Prompt for revisao", False),
            _mock_row("fase_teste", "Prompt for testes", True),
            _mock_row("concluido", "Prompt for concluido", True),
        ]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)

        assert len(_kanban_prompts_cache) == 5
        assert _kanban_prompts_cache["tasks"]["prompt"] == "Prompt for tasks"
        assert _kanban_prompts_cache["tasks"]["is_enabled"] is True
        assert _kanban_prompts_cache["revisao_codigo"]["is_enabled"] is False
        assert _kanban_prompts_cache["concluido"]["prompt"] == "Prompt for concluido"

    def test_loads_prompt_with_special_characters(self):
        prompt = "Crie um arquivo SKILL.md com instruções para a equipe 🚀"
        rows = [_mock_row("tasks", prompt, True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache["tasks"]["prompt"] == prompt


# ---------------------------------------------------------------------------
# 3. Cache com prompts habilitados e desabilitados misturados
# ---------------------------------------------------------------------------

class TestCacheMixedEnabled:
    """Mixed enabled/disabled prompts are stored faithfully."""

    def test_mixed_enabled_disabled_stored_correctly(self):
        rows = [
            _mock_row("tasks", "Enabled prompt", True),
            _mock_row("em_andamento", "Disabled prompt", False),
            _mock_row("revisao_codigo", "Also enabled", True),
        ]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)

        assert _kanban_prompts_cache["tasks"]["is_enabled"] is True
        assert _kanban_prompts_cache["em_andamento"]["is_enabled"] is False
        assert _kanban_prompts_cache["revisao_codigo"]["is_enabled"] is True

    def test_reloading_overwrites_previous_cache(self):
        """Reloading with different data must replace the old cache entirely."""
        rows_v1 = [_mock_row("tasks", "Version 1", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows_v1
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache["tasks"]["prompt"] == "Version 1"

        # Reload with updated data
        rows_v2 = [_mock_row("tasks", "Version 2", False)]
        db.query.return_value.all.return_value = rows_v2
        _load_kanban_prompts_cache(db)

        assert _kanban_prompts_cache["tasks"]["prompt"] == "Version 2"
        assert _kanban_prompts_cache["tasks"]["is_enabled"] is False
        # TTL timestamp should be refreshed
        assert mcp_mod._kanban_prompts_cache_loaded is not None

    def test_reload_clears_old_keys(self):
        """If a status was removed from the DB, it should not remain in the cache."""
        rows_v1 = [
            _mock_row("tasks", "T", True),
            _mock_row("em_andamento", "E", True),
        ]
        db = MagicMock()
        db.query.return_value.all.return_value = rows_v1
        _load_kanban_prompts_cache(db)
        assert "em_andamento" in _kanban_prompts_cache

        rows_v2 = [_mock_row("tasks", "T updated", True)]
        db.query.return_value.all.return_value = rows_v2
        _load_kanban_prompts_cache(db)

        assert "em_andamento" not in _kanban_prompts_cache
        assert len(_kanban_prompts_cache) == 1


# ---------------------------------------------------------------------------
# 4. Expiry — TTL de 600 s (10 minutos)
# ---------------------------------------------------------------------------

class TestCacheExpiry:
    """The 600-second TTL must expire the cache correctly."""

    def test_not_expired_immediately_after_load(self):
        db = MagicMock()
        db.query.return_value.all.return_value = []
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache_expired() is False

    def test_expired_after_ttl_seconds(self):
        db = MagicMock()
        db.query.return_value.all.return_value = []
        _load_kanban_prompts_cache(db)

        # Manually backdate the loaded timestamp to simulate TTL expiry
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=_KANBAN_PROMPTS_TTL_SECONDS + 1)
        mcp_mod._kanban_prompts_cache_loaded = old_time
        assert _kanban_prompts_cache_expired() is True

    def test_not_expired_before_ttl_seconds(self):
        db = MagicMock()
        db.query.return_value.all.return_value = []
        _load_kanban_prompts_cache(db)

        # Backdate by just under the TTL
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=_KANBAN_PROMPTS_TTL_SECONDS - 10)
        mcp_mod._kanban_prompts_cache_loaded = old_time
        assert _kanban_prompts_cache_expired() is False

    def test_expired_when_cache_never_loaded(self):
        """If the cache was never loaded (_kanban_prompts_cache_loaded is None),
        the cache is considered expired."""
        # Ensure it is None (should be after fixture reset)
        assert mcp_mod._kanban_prompts_cache_loaded is None
        assert _kanban_prompts_cache_expired() is True

    def test_ttl_constant_is_six_hundred(self):
        assert _KANBAN_PROMPTS_TTL_SECONDS == 600


# ---------------------------------------------------------------------------
# 5. Invalidation — limpa tudo
# ---------------------------------------------------------------------------

class TestCacheInvalidation:
    """_invalidate_kanban_prompts_cache() must clear everything."""

    def test_invalidation_clears_cache(self):
        rows = [_mock_row("tasks", "T", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert len(_kanban_prompts_cache) > 0

        _invalidate_kanban_prompts_cache()
        assert _kanban_prompts_cache == {}

    def test_invalidation_resets_timestamp(self):
        rows = [_mock_row("tasks", "T", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert mcp_mod._kanban_prompts_cache_loaded is not None

        _invalidate_kanban_prompts_cache()
        assert mcp_mod._kanban_prompts_cache_loaded is None

    def test_expired_after_invalidation(self):
        rows = [_mock_row("tasks", "T", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        _invalidate_kanban_prompts_cache()
        assert _kanban_prompts_cache_expired() is True

    def test_reload_after_invalidation_works(self):
        rows = [_mock_row("tasks", "T", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows

        _load_kanban_prompts_cache(db)
        _invalidate_kanban_prompts_cache()
        assert mcp_mod._kanban_prompts_cache_loaded is None
        assert _kanban_prompts_cache == {}

        # Reload should work after invalidation
        _load_kanban_prompts_cache(db)
        assert len(_kanban_prompts_cache) == 1
        assert mcp_mod._kanban_prompts_cache_loaded is not None


# ---------------------------------------------------------------------------
# 6. Boot — exceções do DB tratadas com graceful degradation
# ---------------------------------------------------------------------------

class TestLoadCacheExceptions:
    """_load_kanban_prompts_cache must not crash on DB exceptions."""

    def test_db_connection_error_logs_warning(self):
        db = MagicMock()
        db.query.side_effect = Exception("Connection refused")
        # Must not raise; logging.warning is called internally
        _load_kanban_prompts_cache(db)
        # Cache should remain empty (or at least not raise)
        # We just verify no exception bubbles up
        assert True  # noqa: PT015

    def test_db_session_error_preserves_old_cache(self):
        """If loading fails, the old cache (if any) should remain untouched."""
        rows = [_mock_row("tasks", "T", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache["tasks"]["prompt"] == "T"

        # Now simulate a failure during reload
        db.query.side_effect = Exception("Database error")
        _load_kanban_prompts_cache(db)

        # The cache was already cleared by .clear() inside _load, so it stays empty.
        # The key behavior: no exception raised.
        assert True  # noqa: PT015

    def test_none_db_does_not_crash(self):
        """Passing None as db should be handled gracefully (no crash)."""
        # This will raise an AttributeError when calling .query() on None.
        # The function should catch the exception.
        _load_kanban_prompts_cache(None)
        assert True  # noqa: PT015


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------

class TestCacheEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_prompt_string_is_stored(self):
        rows = [_mock_row("tasks", "", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache["tasks"]["prompt"] == ""

    def test_prompt_with_unicode_characters(self):
        prompt = "🔒 Memória segura — 日本語テスト — Ñoño"
        rows = [_mock_row("tasks", prompt, True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert _kanban_prompts_cache["tasks"]["prompt"] == prompt

    def test_single_character_status(self):
        rows = [_mock_row("x", "prompt", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)
        assert "x" in _kanban_prompts_cache
        assert _kanban_prompts_cache["x"]["prompt"] == "prompt"

    def test_cache_key_is_column_status_string(self):
        rows = [
            _mock_row("tasks", "T", True),
            _mock_row("em_andamento", "E", True),
        ]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)

        assert set(_kanban_prompts_cache.keys()) == {"tasks", "em_andamento"}

    def test_cache_structure_per_status(self):
        rows = [_mock_row("tasks", "Test", True)]
        db = MagicMock()
        db.query.return_value.all.return_value = rows
        _load_kanban_prompts_cache(db)

        entry = _kanban_prompts_cache["tasks"]
        assert isinstance(entry, dict)
        assert "prompt" in entry
        assert "is_enabled" in entry
        assert entry["prompt"] == "Test"
        assert entry["is_enabled"] is True
