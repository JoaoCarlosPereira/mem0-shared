import datetime
import pytest
from unittest.mock import MagicMock, patch

from app.mcp_server import (
    _kanban_prompts_cache,
    _kanban_prompts_cache_expired,
    _load_kanban_prompts_cache,
    _invalidate_kanban_prompts_cache,
)

class DummyPrompt:
    def __init__(self, column_status, prompt, is_enabled):
        self.column_status = column_status
        self.prompt = prompt
        self.is_enabled = is_enabled

class TestKanbanPromptsCache:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        # Reset cache before/after each test
        _invalidate_kanban_prompts_cache()
        yield
        _invalidate_kanban_prompts_cache()

    def test_cache_expired_initially(self):
        # Cache should be expired when never loaded
        assert _kanban_prompts_cache_expired() is True

    def test_cache_not_expired_within_ttl(self):
        import app.mcp_server
        # Load the cache and mock load time to be current
        app.mcp_server._kanban_prompts_cache_loaded = datetime.datetime.now(datetime.UTC)
        assert _kanban_prompts_cache_expired() is False

    def test_cache_expired_after_ttl(self):
        import app.mcp_server
        # Mock load time to be 11 minutes ago (660 seconds)
        app.mcp_server._kanban_prompts_cache_loaded = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=660)
        assert _kanban_prompts_cache_expired() is True

    def test_load_kanban_prompts_cache(self):
        # Mock DB session
        db_mock = MagicMock()
        prompts = [
            DummyPrompt("em_andamento", "Prompt 1", True),
            DummyPrompt("revisao_codigo", "Prompt 2", False),
        ]
        db_mock.query().all.return_value = prompts

        _load_kanban_prompts_cache(db_mock)

        assert len(_kanban_prompts_cache) == 2
        assert _kanban_prompts_cache["em_andamento"] == {"prompt": "Prompt 1", "is_enabled": True}
        assert _kanban_prompts_cache["revisao_codigo"] == {"prompt": "Prompt 2", "is_enabled": False}
        
        import app.mcp_server
        assert app.mcp_server._kanban_prompts_cache_loaded is not None

    def test_invalidate_kanban_prompts_cache(self):
        import app.mcp_server
        # Seed cache
        app.mcp_server._kanban_prompts_cache["tasks"] = {"prompt": "Test", "is_enabled": True}
        app.mcp_server._kanban_prompts_cache_loaded = datetime.datetime.now(datetime.UTC)

        _invalidate_kanban_prompts_cache()

        assert len(_kanban_prompts_cache) == 0
        assert app.mcp_server._kanban_prompts_cache_loaded is None

    def test_load_cache_warning_on_failure(self):
        # Mock DB session query to raise an exception
        db_mock = MagicMock()
        db_mock.query.side_effect = Exception("DB Connection Error")

        with patch("logging.warning") as mock_warning:
            _load_kanban_prompts_cache(db_mock)
            mock_warning.assert_called_once()
            args, _ = mock_warning.call_args
            assert "Failed to load kanban column prompts cache" in args[0]
            assert "DB Connection Error" in str(args[1])
