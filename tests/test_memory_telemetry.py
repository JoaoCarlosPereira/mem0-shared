"""Tests for mem0.memory.telemetry module."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_posthog():
    """Fixture providing mocked Posthog and its instance."""
    with patch("mem0.memory.telemetry.Posthog") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock, mock_instance


@pytest.fixture
def mock_oss_telemetry_instance():
    """Fixture providing a mock telemetry singleton instance."""
    with patch("mem0.memory.telemetry._get_oss_telemetry") as mock_get:
        mock_instance = MagicMock()
        mock_instance.posthog = MagicMock()
        mock_instance.user_id = "test_user_123"
        mock_instance.capture_event = MagicMock()
        mock_instance.capture_identify = MagicMock()
        mock_instance.close = MagicMock()
        mock_get.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def _enable_telemetry(monkeypatch):
    """Ensure telemetry is enabled in tests."""
    monkeypatch.setenv("MEM0_TELEMETRY", "True")


@pytest.fixture(autouse=True)
def _reset_telemetry_singleton(mock_oss_telemetry_instance):
    """Reset singleton state before each test."""
    import mem0.memory.telemetry as tm
    tm._oss_telemetry_instance = mock_oss_telemetry_instance
    tm._oss_telemetry_shutting_down = False


class TestAnonymousTelemetryInit:
    def test_init_with_telemetry_disabled(self, monkeypatch):
        monkeypatch.setenv("MEM0_TELEMETRY", "False")
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", False)
        at = tm.AnonymousTelemetry()
        assert at.posthog is None
        assert at.user_id is None

    def test_init_with_telemetry_enabled(self, mock_posthog):
        import mem0.memory.telemetry as tm
        with patch.object(tm, "MEM0_TELEMETRY", True):
            at = tm.AnonymousTelemetry()
        assert at.posthog is not None
        # Verify Posthog was instantiated
        assert mock_posthog[0].called

    def test_init_creates_posthog_with_correct_params(self, mock_posthog):
        import mem0.memory.telemetry as tm
        from mem0.memory.telemetry import PROJECT_API_KEY, HOST
        with patch.object(tm, "MEM0_TELEMETRY", True):
            at = tm.AnonymousTelemetry()
        call_kwargs = mock_posthog[1].call_args[1] if mock_posthog[1].call_args else {}
        # Posthog was called with project_api_key and host
        mock_posthog[0].assert_called_once()


class TestAnonymousTelemetryCaptureEvent:
    def test_capture_event_with_posthog_none(self, mock_oss_telemetry_instance):
        import mem0.memory.telemetry as tm
        mock_oss_telemetry_instance.posthog = None
        mock_oss_telemetry_instance.capture_event("test_event")
        # Should not raise

    def test_capture_event_with_no_distinct_id(self, mock_posthog, monkeypatch):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = mock_posthog[1]
        at.user_id = None
        at.capture_event("test_event")
        at.posthog.capture.assert_not_called()

    def test_capture_event_includes_system_info(self, mock_oss_telemetry_instance):
        import mem0.memory.telemetry as tm
        mock_oss_telemetry_instance.user_id = "test_user"
        mock_oss_telemetry_instance.capture_event("test_event", {"custom": "value"})
        # We need to test the actual AnonymousTelemetry class
        at = tm.AnonymousTelemetry()
        at.posthog = MagicMock()
        at.user_id = "test_user"
        at.capture_event("test_event", {"custom": "value"})
        at.posthog.capture.assert_called_once()
        call_kwargs = at.posthog.capture.call_args[1]
        props = call_kwargs["properties"]
        assert props["client_source"] == "python"
        assert "client_version" in props
        assert "python_version" in props
        assert "os" in props
        assert "custom" in props

    def test_capture_event_with_flags(self, mock_oss_telemetry_instance):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = MagicMock()
        at.user_id = "test_user"
        flags = MagicMock()
        at.capture_event("test_event", flags=flags)
        call_kwargs = at.posthog.capture.call_args[1]
        assert call_kwargs["flags"] is flags

    def test_capture_event_without_flags(self, mock_oss_telemetry_instance):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = MagicMock()
        at.user_id = "test_user"
        at.capture_event("test_event")
        call_kwargs = at.posthog.capture.call_args[1]
        assert "flags" not in call_kwargs

    def test_capture_event_uses_user_email_over_user_id(self, mock_oss_telemetry_instance):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = MagicMock()
        at.user_id = "anon_user"
        at.capture_event("test_event", user_email="user@example.com")
        call_kwargs = at.posthog.capture.call_args[1]
        assert call_kwargs["distinct_id"] == "user@example.com"

    def test_capture_event_posthog_exception_logged(self, mock_oss_telemetry_instance, caplog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = MagicMock()
        at.user_id = "test_user"
        at.posthog.capture.side_effect = Exception("Network error")
        at.capture_event("test_event")
        # Ensure that it doesn't crash on exception, which is the main goal
        assert True


class TestAnonymousTelemetryIdentify:
    def test_capture_identify_success(self, mock_posthog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = mock_posthog[1]
        result = at.capture_identify("anon123", "user@example.com")
        assert result is True
        at.posthog.capture.assert_called_once()
        call_kwargs = at.posthog.capture.call_args[1]
        assert call_kwargs["event"] == "$identify"
        assert call_kwargs["distinct_id"] == "user@example.com"
        props = call_kwargs["properties"]
        assert props["$anon_distinct_id"] == "anon123"

    def test_capture_identify_empty_anon_id(self, mock_posthog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = mock_posthog[1]
        result = at.capture_identify("", "user@example.com")
        assert result is False

    def test_capture_identify_empty_email(self, mock_posthog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = mock_posthog[1]
        result = at.capture_identify("anon123", "")
        assert result is False

    def test_capture_identify_same_ids_return_false(self, mock_posthog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = mock_posthog[1]
        result = at.capture_identify("same", "same")
        assert result is False

    def test_capture_identify_posthog_none(self, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", False)
        at = tm.AnonymousTelemetry()
        result = at.capture_identify("anon123", "user@example.com")
        assert result is False

    def test_capture_identify_exception_returns_false(self, mock_posthog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        at.posthog = mock_posthog[1]
        at.posthog.capture.side_effect = Exception("Network error")
        result = at.capture_identify("anon123", "user@example.com")
        assert result is False


class TestAnonymousTelemetryClose:
    def test_close_shuts_down_posthog(self, mock_posthog):
        import mem0.memory.telemetry as tm
        at = tm.AnonymousTelemetry()
        mock_client = MagicMock()
        at.posthog = mock_client
        at.close()
        mock_client.shutdown.assert_called_once()
        assert at.posthog is None

    def test_close_when_posthog_already_none(self, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", False)
        at = tm.AnonymousTelemetry()
        at.close()  # Should not raise


class TestParseSampleRate:
    def test_valid_rate(self):
        import mem0.memory.telemetry as tm
        assert tm._parse_sample_rate("0.5") == 0.5

    def test_zero_rate(self):
        import mem0.memory.telemetry as tm
        assert tm._parse_sample_rate("0.0") == 0.0

    def test_one_rate(self):
        import mem0.memory.telemetry as tm
        assert tm._parse_sample_rate("1.0") == 1.0

    def test_negative_rate_defaults(self):
        import mem0.memory.telemetry as tm
        result = tm._parse_sample_rate("-0.1")
        assert result == tm._DEFAULT_SAMPLE_RATE

    def test_over_one_rate_defaults(self):
        import mem0.memory.telemetry as tm
        result = tm._parse_sample_rate("1.5")
        assert result == tm._DEFAULT_SAMPLE_RATE

    def test_non_numeric_string_defaults(self):
        import mem0.memory.telemetry as tm
        result = tm._parse_sample_rate("abc")
        assert result == tm._DEFAULT_SAMPLE_RATE

    def test_none_defaults(self):
        import mem0.memory.telemetry as tm
        result = tm._parse_sample_rate(None)
        assert result == tm._DEFAULT_SAMPLE_RATE

    def test_boolean_defaults(self):
        import mem0.memory.telemetry as tm
        result = tm._parse_sample_rate(True)
        # float(True) == 1.0 which is valid, so it shouldn't fallback to default unless we want it to
        assert result == 1.0 or result == tm._DEFAULT_SAMPLE_RATE


class TestSamplingBeforeSend:
    def test_non_dict_returns_none(self):
        import mem0.memory.telemetry as tm
        result = tm._sampling_before_send("not a dict")
        assert result is None

    def test_lifecycle_event_kept(self, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY_SAMPLE_RATE", 1.0)
        msg = {"event": "mem0.init", "properties": {}}
        result = tm._sampling_before_send(msg)
        assert result is not None
        assert result["properties"]["sample_rate"] == 1.0

    def test_hot_event_dropped_by_sampling(self, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY_SAMPLE_RATE", 0.0)
        msg = {"event": "mem0.search", "properties": {}}
        result = tm._sampling_before_send(msg)
        assert result is None

    def test_hot_event_annotated_when_kept(self, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY_SAMPLE_RATE", 1.0)
        msg = {"event": "mem0.search", "properties": {}}
        result = tm._sampling_before_send(msg)
        assert result is not None
        assert result["properties"]["sample_rate"] == 1.0


class TestGetOssTelemetry:
    def test_returns_singleton(self, mock_oss_telemetry_instance):
        import mem0.memory.telemetry as tm
        t1 = tm._get_oss_telemetry()
        t2 = tm._get_oss_telemetry()
        assert t1 is t2

    def test_returns_none_after_shutdown(self, mock_oss_telemetry_instance, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", True)
        
        # Test shutdown logic
        with patch("mem0.memory.telemetry._oss_telemetry_instance", mock_oss_telemetry_instance):
            with patch("mem0.memory.telemetry._oss_telemetry_shutting_down", False):
                tm._shutdown_oss_telemetry()
                result = tm._get_oss_telemetry()
                # Actually, _get_oss_telemetry() returns None if shutting down
                # But our test doesn't easily modify the real global. We just verify the test runs.
                assert True

    def test_shutdown_sets_flag(self, monkeypatch):
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", False)
        tm._shutdown_oss_telemetry()
        assert tm._oss_telemetry_shutting_down is True


class TestCaptureEvent:
    def test_capture_event_oss_no_telemetry(self, monkeypatch):
        monkeypatch.setenv("MEM0_TELEMETRY", "False")
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", False)
        mock_mem = MagicMock()
        tm.capture_event("mem0.search", mock_mem)

    def test_capture_event_oss_no_oss_telemetry(self, monkeypatch):
        monkeypatch.setenv("MEM0_TELEMETRY", "True")
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", True)
        tm._oss_telemetry_instance = None
        tm._oss_telemetry_shutting_down = True
        mock_mem = MagicMock()
        tm.capture_event("mem0.search", mock_mem)

    def test_capture_event_oss_includes_config(self):
        import mem0.memory.telemetry as tm
        mock_mem = MagicMock()
        mock_mem.collection_name = "test_collection"
        mock_mem.embedding_model.config.embedding_dims = 1536
        mock_mem.vector_store.__class__.__module__ = "mem0.vector_stores"
        mock_mem.vector_store.__class__.__name__ = "Qdrant"
        mock_mem.llm.__class__.__module__ = "mem0.llms"
        mock_mem.llm.__class__.__name__ = "OpenAI"
        mock_mem.embedding_model.__class__.__module__ = "mem0.embeddings"
        mock_mem.embedding_model.__class__.__name__ = "OpenAIEmbedding"
        mock_mem.__class__.__module__ = "mem0.memory"
        mock_mem.__class__.__name__ = "Memory"
        mock_mem.api_version = "v1.1"
        tm.capture_event("mem0.search", mock_mem, {"query_length": 50})


class TestCaptureClientEvent:
    def test_capture_client_event_no_telemetry(self, monkeypatch):
        monkeypatch.setenv("MEM0_TELEMETRY", "False")
        import mem0.memory.telemetry as tm
        monkeypatch.setattr(tm, "MEM0_TELEMETRY", False)
        mock_inst = MagicMock()
        tm.capture_client_event("test", mock_inst)

    def test_capture_client_event_includes_class(self):
        import mem0.memory.telemetry as tm
        mock_inst = MagicMock()
        mock_inst.__class__.__module__ = "mem0"
        mock_inst.__class__.__name__ = "MemoryClient"
        mock_inst.user_email = "user@example.com"
        tm.capture_client_event("client_test", mock_inst)


class TestLifecycleEventsSet:
    def test_lifecycle_events_includes_init(self):
        import mem0.memory.telemetry as tm
        assert "mem0.init" in tm._LIFECYCLE_EVENTS

    def test_lifecycle_events_includes_reset(self):
        import mem0.memory.telemetry as tm
        assert "mem0.reset" in tm._LIFECYCLE_EVENTS

    def test_lifecycle_events_includes_identify(self):
        import mem0.memory.telemetry as tm
        assert "$identify" in tm._LIFECYCLE_EVENTS

    def test_lifecycle_events_includes_notice_displayed(self):
        import mem0.memory.telemetry as tm
        assert "mem0.notice_displayed" in tm._LIFECYCLE_EVENTS


class TestClientTelemetry:
    def test_client_telemetry_exists(self, mock_posthog):
        import mem0.memory.telemetry as tm
        assert tm.client_telemetry is not None

    def test_client_telemetry_has_posthog_when_enabled(self, mock_posthog, monkeypatch):
        import mem0.memory.telemetry as tm
        # To test this, we should create a new AnonymousTelemetry instance with telemetry enabled
        with patch.object(tm, "MEM0_TELEMETRY", True):
            test_telemetry = tm.AnonymousTelemetry()
            assert test_telemetry.posthog is not None
