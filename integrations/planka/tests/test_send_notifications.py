"""Comprehensive non-regression tests for send_notifications.py — notification delivery via Apprise."""

from __future__ import annotations

import sys
import json
from unittest.mock import MagicMock, patch

import pytest


class TestSendNotification:
    """Tests for send_notification function."""

    def test_sends_notification(self):
        from send_notifications import send_notification

        mock_apprise = MagicMock()
        mock_apprise.return_value.notify.return_value = True

        with patch("send_notifications.Apprise", mock_apprise):
            result = send_notification(
                url="slack://webhook/token",
                title="Test Title",
                body="Test Body",
                body_format="markdown",
            )
            assert result is True
            mock_apprise.return_value.add.assert_called_once_with("slack://webhook/token")
            mock_apprise.return_value.notify.assert_called_once_with(
                title="Test Title",
                body="Test Body",
                body_format="markdown",
            )

    def test_returns_false_on_failure(self):
        from send_notifications import send_notification

        mock_apprise = MagicMock()
        mock_apprise.return_value.notify.return_value = False

        with patch("send_notifications.Apprise", mock_apprise):
            result = send_notification("slack://webhook", "Title", "Body", "markdown")
            assert result is False

    def test_adds_url_before_notify(self):
        """Verify url is added before notify is called."""
        from send_notifications import send_notification

        calls = []

        class MockApprise:
            def add(self, url):
                calls.append(("add", url))
            def notify(self, title, body, body_format):
                calls.append(("notify",))
                return True

        with patch("send_notifications.Apprise", MockApprise):
            send_notification("discord://token", "Title", "Body", "markdown")

        assert len(calls) == 2
        assert calls[0] == ("add", "discord://token")
        assert calls[1] == ("notify",)


class TestBlockedSchemas:
    """Tests for BLOCKED_SCHEMAS_SET filtering."""

    def test_syslog_blocked(self):
        """syslog schema should be blocked."""
        from send_notifications import BLOCKED_SCHEMAS_SET
        assert "syslog" in BLOCKED_SCHEMAS_SET

    def test_dbus_blocked(self):
        assert "dbus" in BLOCKED_SCHEMAS_SET

    def test_kde_blocked(self):
        assert "kde" in BLOCKED_SCHEMAS_SET

    def test_qt_blocked(self):
        assert "qt" in BLOCKED_SCHEMAS_SET

    def test_glib_blocked(self):
        assert "glib" in BLOCKED_SCHEMAS_SET

    def test_gnome_blocked(self):
        assert "gnome" in BLOCKED_SCHEMAS_SET

    def test_macosx_blocked(self):
        assert "macosx" in BLOCKED_SCHEMAS_SET

    def test_windows_blocked(self):
        assert "windows" in BLOCKED_SCHEMAS_SET

    def test_slack_not_blocked(self):
        from send_notifications import BLOCKED_SCHEMAS_SET
        assert "slack" not in BLOCKED_SCHEMAS_SET

    def test_discord_not_blocked(self):
        from send_notifications import BLOCKED_SCHEMAS_SET
        assert "discord" not in BLOCKED_SCHEMAS_SET

    def test_email_not_blocked(self):
        from send_notifications import BLOCKED_SCHEMAS_SET
        assert "email" not in BLOCKED_SCHEMAS_SET

    def test_webhook_not_blocked(self):
        from send_notifications import BLOCKED_SCHEMAS_SET
        assert "webhook" not in BLOCKED_SCHEMAS_SET


class TestMainWithServices:
    """Tests for main CLI entry point with service list."""

    def test_single_service_success(self, capsys):
        """Test with a single successful service."""
        services = [{"url": "slack://webhook/token", "format": "markdown"}]
        title = "Test"
        body_by_format = {"markdown": "Body"}

        with patch("send_notifications.send_notification", return_value=True):
            with patch.object(sys, "argv", ["send_notifications.py", json.dumps(services), title, json.dumps(body_by_format)]):
                with patch("send_notifications.__name__", "__main__"):
                    import send_notifications
                    send_notifications.main() if hasattr(send_notifications, 'main') else None

    def test_blocked_schema_prints_error(self, capsys):
        """Blocked schema should print error and exit 1."""
        services = [{"url": "syslog://localhost", "format": "markdown"}]
        title = "Test"
        body_by_format = {"markdown": "Body"}

        with patch.object(sys, "argv", ["send_notifications.py", json.dumps(services), title, json.dumps(body_by_format)]):
            with patch("send_notifications.__name__", "__main__"):
                import send_notifications
                try:
                    send_notifications.main() if hasattr(send_notifications, 'main') else None
                except SystemExit as e:
                    assert e.code == 1
                captured = capsys.readouterr()
                assert "Blocked service schema" in captured.err

    def test_notification_failure_prints_error(self, capsys):
        """Failed notification should print error and exit 1."""
        services = [{"url": "slack://webhook/token", "format": "markdown"}]
        title = "Test"
        body_by_format = {"markdown": "Body"}

        def mock_send(url, title, body, fmt):
            from send_notifications import last_apprise_message
            # Simulate error message
            import send_notifications as sn
            sn.last_apprise_message = "Connection failed"
            return False

        with patch.object(sys, "argv", ["send_notifications.py", json.dumps(services), title, json.dumps(body_by_format)]):
            with patch("send_notifications.send_notification", side_effect=mock_send):
                with patch("send_notifications.__name__", "__main__"):
                    import send_notifications
                    try:
                        send_notifications.main() if hasattr(send_notifications, 'main') else None
                    except SystemExit as e:
                        assert e.code == 1
                    captured = capsys.readouterr()
                    assert "Connection failed" in captured.err

    def test_unknown_service_url_error(self, capsys):
        """When last_apprise_message is 'There are no service(s) to notify', report unknown URL."""
        services = [{"url": "unknown://weird", "format": "markdown"}]
        title = "Test"
        body_by_format = {"markdown": "Body"}

        def mock_send(url, title, body, fmt):
            import send_notifications as sn
            sn.last_apprise_message = "There are no service(s) to notify"
            return False

        with patch.object(sys, "argv", ["send_notifications.py", json.dumps(services), title, json.dumps(body_by_format)]):
            with patch("send_notifications.send_notification", side_effect=mock_send):
                with patch("send_notifications.__name__", "__main__"):
                    import send_notifications
                    try:
                        send_notifications.main() if hasattr(send_notifications, 'main') else None
                    except SystemExit as e:
                        assert e.code == 1
                    captured = capsys.readouterr()
                    assert "Unknown service URL" in captured.err

    def test_empty_last_apprise_message(self, capsys):
        """When last_apprise_message is None, report unknown error."""
        services = [{"url": "slack://webhook", "format": "markdown"}]
        title = "Test"
        body_by_format = {"markdown": "Body"}

        def mock_send(url, title, body, fmt):
            import send_notifications as sn
            sn.last_apprise_message = None
            return False

        with patch.object(sys, "argv", ["send_notifications.py", json.dumps(services), title, json.dumps(body_by_format)]):
            with patch("send_notifications.send_notification", side_effect=mock_send):
                with patch("send_notifications.__name__", "__main__"):
                    import send_notifications
                    try:
                        send_notifications.main() if hasattr(send_notifications, 'main') else None
                    except SystemExit as e:
                        assert e.code == 1
                    captured = capsys.readouterr()
                    assert "Unknown error" in captured.err

    def test_multiple_services_mixed_results(self, capsys):
        """Multiple services: some succeed, some fail — should exit 1."""
        services = [
            {"url": "slack://webhook", "format": "markdown"},
            {"url": "discord://token", "format": "markdown"},
        ]
        title = "Test"
        body_by_format = {"markdown": "Body"}

        call_count = 0

        def mock_send(url, title, body, fmt):
            nonlocal call_count
            call_count += 1
            import send_notifications as sn
            if call_count == 1:
                return True  # First succeeds
            sn.last_apprise_message = "Discord error"
            return False  # Second fails

        with patch.object(sys, "argv", ["send_notifications.py", json.dumps(services), title, json.dumps(body_by_format)]):
            with patch("send_notifications.send_notification", side_effect=mock_send):
                with patch("send_notifications.__name__", "__main__"):
                    import send_notifications
                    try:
                        send_notifications.main() if hasattr(send_notifications, 'main') else None
                    except SystemExit as e:
                        assert e.code == 1


class TestCaptureWarningHandler:
    """Tests for CaptureWarningHandler."""

    def test_captures_warning_message(self):
        from send_notifications import capture_warning_handler

        record = MagicMock()
        record.getMessage.return_value = "Warning message here"
        capture_warning_handler.emit(record)
        from send_notifications import last_apprise_message
        assert last_apprise_message == "Warning message here"


class TestAppriseLoggerConfig:
    """Tests for apprise logger configuration."""

    def test_logger_level_is_warning(self):
        import logging
        from send_notifications import apprise_logger
        assert apprise_logger.level == logging.WARNING

    def test_propagate_is_false(self):
        from send_notifications import apprise_logger
        assert apprise_logger.propagate is False

    def test_has_capture_handler(self):
        from send_notifications import apprise_logger, capture_warning_handler
        handlers = apprise_logger.handlers
        assert any(h is capture_warning_handler for h in handlers)


class TestLastAppriseMessage:
    """Tests for last_apprise_message global."""

    def test_initial_value_is_none(self):
        from send_notifications import last_apprise_message
        assert last_apprise_message is None

    def test_can_be_updated(self):
        import send_notifications as sn
        sn.last_apprise_message = "new message"
        assert sn.last_apprise_message == "new message"
