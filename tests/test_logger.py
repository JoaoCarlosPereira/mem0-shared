"""Tests for mem0.utils.logger — OpLogger, op_context, set_op_ctx, clear_op_ctx, _Timer."""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from mem0.utils.logger import (
    OpLogger,
    _Timer,
    clear_op_ctx,
    op_context,
    op_logger,
    set_op_ctx,
)


class TestTimer:
    """Tests for _Timer."""

    def test_timer_elapsed_ms_increases(self):
        t = _Timer()
        time.sleep(0.05)
        elapsed = t.elapsed_ms
        assert elapsed > 0

    def test_timer_since_last_ms(self):
        t = _Timer()
        time.sleep(0.03)
        s1 = t.since_last_ms
        time.sleep(0.03)
        s2 = t.since_last_ms
        assert s1 > 0
        assert s2 > 0

    def test_timer_reset(self):
        t = _Timer()
        time.sleep(0.03)
        t.reset()
        elapsed = t.elapsed_ms
        assert elapsed < 50  # reset just happened

    def test_timer_elapsed_ms_returns_float(self):
        t = _Timer()
        result = t.elapsed_ms
        assert isinstance(result, float)


class TestOpContext:
    """Tests for op_context context manager."""

    def setup_method(self):
        clear_op_ctx()

    def teardown_method(self):
        clear_op_ctx()

    def test_op_context_sets_context(self):
        with op_context(operation="add", user_id="u1"):
            from mem0.utils.logger import _op_ctx
            assert _op_ctx.get("operation") == "add"
            assert _op_ctx.get("user_id") == "u1"

    def test_op_context_clears_on_exit(self):
        with op_context(operation="add"):
            pass
        from mem0.utils.logger import _op_ctx
        assert "operation" not in _op_ctx

    def test_op_context_clears_on_exception(self):
        try:
            with op_context(operation="add"):
                raise ValueError("test")
        except ValueError:
            pass
        from mem0.utils.logger import _op_ctx
        assert "operation" not in _op_ctx


class TestSetOpCtx:
    """Tests for set_op_ctx."""

    def setup_method(self):
        clear_op_ctx()

    def teardown_method(self):
        clear_op_ctx()

    def test_set_op_ctx_updates_context(self):
        set_op_ctx(operation="search", run_id="r1")
        from mem0.utils.logger import _op_ctx
        assert _op_ctx["operation"] == "search"

    def test_set_op_ctx_overrides(self):
        set_op_ctx(operation="add")
        set_op_ctx(operation="search")
        from mem0.utils.logger import _op_ctx
        assert _op_ctx["operation"] == "search"

    def test_set_op_ctx_adds_multiple_keys(self):
        set_op_ctx(operation="add")
        set_op_ctx(user_id="u1")
        from mem0.utils.logger import _op_ctx
        assert _op_ctx["operation"] == "add"
        assert _op_ctx["user_id"] == "u1"


class TestClearOpCtx:
    """Tests for clear_op_ctx."""

    def test_clear_op_ctx_clears_all(self):
        set_op_ctx(operation="add", user_id="u1")
        clear_op_ctx()
        from mem0.utils.logger import _op_ctx
        assert len(_op_ctx) == 0


class TestOpLogger:
    """Tests for OpLogger class."""

    def setup_method(self):
        clear_op_ctx()

    def teardown_method(self):
        clear_op_ctx()

    def test_op_logger_creates_logger(self):
        ol = OpLogger("test.module", "add")
        assert ol.operation == "add"
        assert ol._logger is not None

    def test_op_logger_debug(self):
        ol = OpLogger("test.module.debug")
        with patch.object(ol._logger, "debug") as mock_debug:
            ol.debug("test message")
            mock_debug.assert_called_once()

    def test_op_logger_info(self):
        ol = OpLogger("test.module.info")
        with patch.object(ol._logger, "info") as mock_info:
            ol.info("test message")
            mock_info.assert_called_once()

    def test_op_logger_warning(self):
        ol = OpLogger("test.module.warning")
        with patch.object(ol._logger, "warning") as mock_warning:
            ol.warning("test warning")
            mock_warning.assert_called_once()

    def test_op_logger_error(self):
        ol = OpLogger("test.module.error")
        with patch.object(ol._logger, "error") as mock_error:
            ol.error("test error")
            mock_error.assert_called_once()

    def test_op_logger_success(self):
        ol = OpLogger("test.module.success")
        with patch.object(ol._logger, "info") as mock_info:
            ol.success("done")
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert call_args[0][0] == "done"
            assert "extra" in call_args[1]

    def test_op_logger_success_default_message(self):
        ol = OpLogger("test.module.success")
        with patch.object(ol._logger, "info") as mock_info:
            ol.success()
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "Operation completed" in call_args[0][0]

    def test_op_logger_extra_merged(self):
        ol = OpLogger("test.module.extra")
        with patch.object(ol._logger, "info") as mock_info:
            ol.info("msg", user_id="u1", agent_id="a1")
            call_kwargs = mock_info.call_args[1]
            assert "extra" in call_kwargs

    def test_op_logger_includes_op_id(self):
        ol = OpLogger("test.module.opid")
        with patch.object(ol._logger, "info") as mock_info:
            ol.info("msg")
            call_kwargs = mock_info.call_args[1]
            extra = call_kwargs.get("extra", {})
            assert "op_id" in extra

    def test_op_logger_with_op_context(self):
        ol = OpLogger("test.module.with_ctx")
        with op_context(operation="add", user_id="u1"):
            with patch.object(ol._logger, "info") as mock_info:
                ol.info("msg")
                call_kwargs = mock_info.call_args[1]
                extra = call_kwargs.get("extra", {})
                assert extra.get("operation") == "add"

    def test_op_logger_log_start(self):
        ol = OpLogger("test.module.log_start")
        with patch.object(ol._logger, "info") as mock_info:
            ol.log_start("pipeline started")
            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            extra = call_kwargs.get("extra", {})
            assert extra.get("phase") == "start"
            assert extra.get("status") == "started"

    def test_op_logger_log_end(self):
        ol = OpLogger("test.module.log_end")
        with patch.object(ol._logger, "info") as mock_info:
            ol.log_end("pipeline completed")
            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            extra = call_kwargs.get("extra", {})
            assert extra.get("phase") == "end"
            assert extra.get("status") == "completed"

    def test_op_logger_log_phase(self):
        ol = OpLogger("test.module.log_phase")
        with patch.object(ol._logger, "info") as mock_info:
            ol.log_phase(1, "phase 1 started")
            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            extra = call_kwargs.get("extra", {})
            assert str(extra.get("phase")) == "1"
            assert extra.get("status") == "phase_start"

    def test_op_logger_log_phase_end(self):
        ol = OpLogger("test.module.log_phase_end")
        with patch.object(ol._logger, "info") as mock_info:
            ol.log_phase_end(1, "phase 1 done", elapsed_ms=123.456)
            mock_info.assert_called_once()
            call_kwargs = mock_info.call_args[1]
            extra = call_kwargs.get("extra", {})
            assert str(extra.get("phase")) == "1"
            assert extra.get("status") == "phase_end"
            assert extra.get("elapsed_ms") == 123.46  # rounded to 2 decimals

    def test_op_logger_timer_returns_timer(self):
        ol = OpLogger("test.module.timer")
        timer = ol.timer()
        assert isinstance(timer, _Timer)

    def test_op_logger_default_meta_filters_none_values(self):
        ol = OpLogger("test.module.meta")
        meta = ol._meta({"user_id": "u1", "agent_id": None})
        assert "user_id" in meta
        assert "agent_id" not in meta

    def test_op_logger_meta_uses_existing_op_id(self):
        clear_op_ctx()
        set_op_ctx(op_id="custom-id")
        ol = OpLogger("test.module.existing_opid")
        meta = ol._meta()
        assert meta["op_id"] == "custom-id"
        clear_op_ctx()


class TestOpLoggerFactory:
    """Tests for op_logger factory function."""

    def test_op_logger_returns_instance(self):
        ol = op_logger("test.factory")
        assert isinstance(ol, OpLogger)
        assert ol.operation == ""

    def test_op_logger_with_operation(self):
        ol = op_logger("test.factory.op", "add")
        assert ol.operation == "add"

    def test_op_logger_creates_new_logger_each_call(self):
        ol1 = op_logger("test.factory.unique")
        ol2 = op_logger("test.factory.unique")
        assert ol1 is not ol2
