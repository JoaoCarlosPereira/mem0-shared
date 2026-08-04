"""Tests for mem0.client.utils — APIError, api_error_handler."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mem0.client.utils import APIError, api_error_handler
from mem0.exceptions import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    ValidationError,
)


class TestAPIError:
    def test_api_error_is_exception(self):
        assert issubclass(APIError, Exception)

    def test_api_error_message(self):
        err = APIError("something failed")
        assert str(err) == "something failed"

    def test_api_error_no_args(self):
        err = APIError()
        assert str(err) == ""

    def test_api_error_inheritance(self):
        err = APIError("test")
        assert isinstance(err, Exception)


class TestApiErrorHandlerDecorator:
    def test_success_returns_value(self):
        @api_error_handler
        def func():
            return {"status": "ok"}

        result = func()
        assert result == {"status": "ok"}

    def test_success_preserves_function_name(self):
        @api_error_handler
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_http_status_error_400_becomes_validation_error(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 400
            resp.text = "Bad request"
            resp.headers = {}
            raise httpx.HTTPStatusError(
                "bad", request=MagicMock(), response=resp
            )

        with pytest.raises(ValidationError):
            func()

    def test_http_status_error_401_becomes_authentication_error(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 401
            resp.text = "Unauthorized"
            resp.headers = {}
            raise httpx.HTTPStatusError(
                "unauth", request=MagicMock(), response=resp
            )

        with pytest.raises(AuthenticationError):
            func()

    def test_http_status_error_429_becomes_rate_limit_error(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "Too many requests"
            resp.headers = {}
            raise httpx.HTTPStatusError(
                "rate", request=MagicMock(), response=resp
            )

        with pytest.raises(RateLimitError):
            func()

    def test_http_status_error_404_becomes_memory_not_found_error(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 404
            resp.text = "Not found"
            resp.headers = {}
            raise httpx.HTTPStatusError(
                "not found", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception):
            func()

    def test_http_status_error_500_becomes_memory_error(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 500
            resp.text = "Internal error"
            resp.headers = {}
            raise httpx.HTTPStatusError(
                "server", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception):
            func()

    def test_http_status_error_parses_json_detail(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 400
            resp.text = json.dumps({"detail": "Invalid field: user_id"})
            resp.headers = {"content-type": "application/json"}
            raise httpx.HTTPStatusError(
                "bad", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception) as exc_info:
            func()
        assert "Invalid field: user_id" in str(exc_info.value.message)

    def test_http_status_error_429_with_retry_after_header(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "Rate limit exceeded"
            resp.headers = {"Retry-After": "60", "X-RateLimit-Limit": "100"}
            raise httpx.HTTPStatusError(
                "rate", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception) as exc_info:
            func()
        assert exc_info.value.error_code == "HTTP_429"

    def test_http_status_error_429_with_numeric_retry_after(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "Rate limit"
            resp.headers = {"Retry-After": "60"}
            raise httpx.HTTPStatusError(
                "rate", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception) as exc_info:
            func()
        # Should include retry_after in debug_info
        assert "retry_after" in str(exc_info.value.debug_info)

    def test_request_error_timeout_becomes_network_error(self):
        @api_error_handler
        def func():
            raise httpx.TimeoutException("Connection timed out")

        with pytest.raises(NetworkError) as exc_info:
            func()
        assert exc_info.value.error_code == "NET_TIMEOUT"

    def test_request_error_connect_becomes_network_error(self):
        @api_error_handler
        def func():
            raise httpx.ConnectError("Connection refused")

        with pytest.raises(NetworkError) as exc_info:
            func()
        assert exc_info.value.error_code == "NET_CONNECT"

    def test_request_error_generic_becomes_network_error(self):
        @api_error_handler
        def func():
            raise httpx.ConnectError("Generic connect error")

        with pytest.raises(NetworkError) as exc_info:
            func()
        assert exc_info.value.error_code == "NET_CONNECT"

    def test_non_http_exceptions_pass_through(self):
        @api_error_handler
        def func():
            raise ValueError("custom error")

        with pytest.raises(ValueError, match="custom error"):
            func()

    def test_http_status_error_with_non_json_response(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 500
            resp.text = "Internal Server Error"
            resp.headers = {"content-type": "text/html"}
            raise httpx.HTTPStatusError(
                "err", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception):
            func()

    def test_rate_limit_headers_parsed(self):
        @api_error_handler
        def func():
            resp = MagicMock()
            resp.status_code = 429
            resp.text = "Rate limit"
            resp.headers = {
                "Retry-After": "30",
                "X-RateLimit-Limit": "1000",
                "X-RateLimit-Remaining": "5",
                "X-RateLimit-Reset": "1700000000",
            }
            raise httpx.HTTPStatusError(
                "rate", request=MagicMock(), response=resp
            )

        with pytest.raises(Exception) as exc_info:
            func()
        assert exc_info.value.error_code == "HTTP_429"

    def test_debug_info_includes_url_and_method(self):
        @api_error_handler
        def func():
            mock_request = MagicMock()
            mock_request.url = httpx.URL("https://api.mem0.ai/v1/memories/")
            mock_request.method = "POST"
            resp = MagicMock()
            resp.status_code = 400
            resp.text = "Bad request"
            resp.headers = {}
            raise httpx.HTTPStatusError(
                "bad", request=mock_request, response=resp
            )

        with pytest.raises(Exception) as exc_info:
            func()
        assert "url" in str(exc_info.value.debug_info)
        assert "method" in str(exc_info.value.debug_info)
