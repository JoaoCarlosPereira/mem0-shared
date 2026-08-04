"""Tests for mem0.exceptions — exception hierarchy and create_exception_from_response."""

import pytest

from mem0.exceptions import (
    AuthenticationError,
    CacheError,
    ConfigurationError,
    DatabaseError,
    DependencyError,
    EmbeddingError,
    HTTP_STATUS_TO_EXCEPTION,
    LLMError,
    MemoryCorruptionError,
    MemoryError,
    MemoryNotFoundError,
    MemoryQuotaExceededError,
    NetworkError,
    RateLimitError,
    ValidationError,
    VectorSearchError,
    VectorStoreError,
    create_exception_from_response,
)


class TestMemoryError:
    """Tests for the base MemoryError class."""

    def test_init_with_all_fields(self):
        """MemoryError initializes with all fields."""
        e = MemoryError(
            message="test",
            error_code="TEST_001",
            details={"key": "value"},
            suggestion="try again",
            debug_info={"info": "data"},
        )
        assert e.message == "test"
        assert e.error_code == "TEST_001"
        assert e.details == {"key": "value"}
        assert e.suggestion == "try again"
        assert e.debug_info == {"info": "data"}

    def test_init_with_defaults(self):
        """MemoryError defaults details and debug_info to empty dicts."""
        e = MemoryError("test", "TEST_001")
        assert e.details == {}
        assert e.debug_info == {}
        assert e.suggestion is None

    def test_repr(self):
        """MemoryError.__repr__ includes all fields."""
        e = MemoryError("msg", "EC", {"d": 1}, "s", {"di": 2})
        r = repr(e)
        assert "MemoryError" in r
        assert "msg" in r
        assert "EC" in r

    def test_inheritance(self):
        """MemoryError is an Exception."""
        assert issubclass(MemoryError, Exception)

    def test_str(self):
        """str(MemoryError) returns the message."""
        e = MemoryError("hello", "EC")
        assert str(e) == "hello"


class TestExceptionSubclasses:
    """Tests for all exception subclasses."""

    def test_authentication_error(self):
        e = AuthenticationError("auth failed", "AUTH_001")
        assert isinstance(e, MemoryError)
        assert e.message == "auth failed"

    def test_rate_limit_error(self):
        e = RateLimitError("rate limited", "RATE_001")
        assert isinstance(e, MemoryError)

    def test_validation_error(self):
        e = ValidationError("bad input", "VAL_001")
        assert isinstance(e, MemoryError)

    def test_memory_not_found_error(self):
        e = MemoryNotFoundError("not found", "MEM_404")
        assert isinstance(e, MemoryError)

    def test_network_error(self):
        e = NetworkError("timeout", "NET_001")
        assert isinstance(e, MemoryError)

    def test_configuration_error(self):
        e = ConfigurationError("bad config", "CFG_001")
        assert isinstance(e, MemoryError)

    def test_memory_quota_exceeded_error(self):
        e = MemoryQuotaExceededError("quota exceeded", "QUOTA_001")
        assert isinstance(e, MemoryError)

    def test_memory_corruption_error(self):
        e = MemoryCorruptionError("corrupt", "CORRUPT_001")
        assert isinstance(e, MemoryError)

    def test_vector_search_error(self):
        e = VectorSearchError("search failed", "VEC_001")
        assert isinstance(e, MemoryError)

    def test_cache_error(self):
        e = CacheError("cache miss", "CACHE_001")
        assert isinstance(e, MemoryError)

    def test_vector_store_error(self):
        e = VectorStoreError("vs failed", "VECTOR_001")
        assert isinstance(e, MemoryError)
        assert e.error_code == "VECTOR_001"
        assert e.suggestion == "Please check your vector store configuration and connection"

    def test_embedding_error(self):
        e = EmbeddingError("embed failed", "EMBED_001")
        assert isinstance(e, MemoryError)
        assert e.error_code == "EMBED_001"

    def test_llm_error(self):
        e = LLMError("llm failed", "LLM_001")
        assert isinstance(e, MemoryError)
        assert e.error_code == "LLM_001"

    def test_database_error(self):
        e = DatabaseError("db failed", "DB_001")
        assert isinstance(e, MemoryError)
        assert e.error_code == "DB_001"

    def test_dependency_error(self):
        e = DependencyError("deps missing", "DEPS_001")
        assert isinstance(e, MemoryError)
        assert e.error_code == "DEPS_001"


class TestCreateExceptionFromResponse:
    """Tests for create_exception_from_response."""

    @pytest.mark.parametrize("status_code,expected_class", [
        (400, ValidationError),
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, MemoryNotFoundError),
        (408, NetworkError),
        (409, ValidationError),
        (413, MemoryQuotaExceededError),
        (422, ValidationError),
        (429, RateLimitError),
        (500, MemoryError),
        (502, NetworkError),
        (503, NetworkError),
        (504, NetworkError),
    ])
    def test_known_status_codes(self, status_code, expected_class):
        """Known status codes map to the correct exception class."""
        exc = create_exception_from_response(status_code, "error text")
        assert isinstance(exc, expected_class)

    def test_unknown_status_code_defaults_to_memory_error(self):
        """Unknown status codes default to MemoryError."""
        exc = create_exception_from_response(599, "error")
        assert isinstance(exc, MemoryError)
        assert not isinstance(exc, (ValidationError, AuthenticationError))

    def test_error_code_custom(self):
        """Custom error_code is used when provided."""
        exc = create_exception_from_response(400, "err", error_code="CUSTOM")
        assert exc.error_code == "CUSTOM"

    def test_error_code_generated(self):
        """Error code is auto-generated when not provided."""
        exc = create_exception_from_response(404, "err")
        assert exc.error_code == "HTTP_404"

    def test_suggestion_based_on_status(self):
        """Suggestions are based on status code."""
        exc = create_exception_from_response(429, "too many")
        assert "Rate limit" in exc.suggestion

    def test_message_from_response(self):
        """Exception message comes from response_text."""
        exc = create_exception_from_response(500, "Internal server failure")
        assert exc.message == "Internal server failure"

    def test_message_defaults_to_http_text(self):
        """When response_text is empty, uses HTTP code."""
        exc = create_exception_from_response(500, "")
        assert "HTTP 500" in exc.message

    def test_details_passed_through(self):
        """Details dict is passed through."""
        exc = create_exception_from_response(400, "err", details={"field": "x"})
        assert exc.details["field"] == "x"

    def test_debug_info_passed_through(self):
        """Debug info dict is passed through."""
        exc = create_exception_from_response(400, "err", debug_info={"retry": 60})
        assert exc.debug_info["retry"] == 60


class TestHTTP_STATUS_TO_EXCEPTION:
    """Tests for the HTTP_STATUS_TO_EXCEPTION mapping."""

    def test_mapping_contains_expected_keys(self):
        """HTTP_STATUS_TO_EXCEPTION has the expected status codes."""
        assert 400 in HTTP_STATUS_TO_EXCEPTION
        assert 401 in HTTP_STATUS_TO_EXCEPTION
        assert 429 in HTTP_STATUS_TO_EXCEPTION
        assert 500 in HTTP_STATUS_TO_EXCEPTION

    def test_all_values_are_memory_error_subclasses(self):
        """All mapped values are MemoryError subclasses."""
        for status, exc_class in HTTP_STATUS_TO_EXCEPTION.items():
            assert issubclass(exc_class, MemoryError)
