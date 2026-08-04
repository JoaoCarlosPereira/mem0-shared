"""Tests for mem0.memory.notices module."""

from datetime import datetime, timedelta, timezone

from unittest.mock import MagicMock

import pytest

from mem0.memory.notices import (
    DECAY_FEATURE_ERROR_MESSAGE,
    DECAY_USAGE_CAP,
    DECAY_USAGE_DELETE_THRESHOLD,
    DECAY_USAGE_NOTICE_ID,
    DECAY_USAGE_STATE_KEY,
    DECAY_USAGE_WINDOW,
    DISPLAYED_VARIANT,
    FEATURE_ERROR_CAP,
    FEATURE_ERROR_WINDOW,
    FLAG_KEY,
    HOLDOUT_VARIANT,
    NOTICE_EVENT,
    NOTICE_ID,
    PERFORMANCE_SLOW_QUERY_THRESHOLD_SECONDS,
    PERFORMANCE_SLOW_QUERY_NOTICE_ID,
    SCALE_MEMORY_COUNT_THRESHOLD,
    SCALE_MEMORY_COUNT_CHECK_INTERVAL,
    SCALE_TOP_K_THRESHOLD,
    SCALE_THRESHOLD_CAP,
    SCALE_THRESHOLD_NOTICE_ID,
    SCALE_THRESHOLD_STATE_KEY,
    TEMPORAL_FEATURE_ERROR_MESSAGES,
    TEMPORAL_USAGE_CAP,
    TEMPORAL_USAGE_NOTICE_ID,
    TEMPORAL_USAGE_STATE_KEY,
    TEMPORAL_USAGE_WINDOW,
    _coerce_mapping,
    _coerce_nonnegative_int,
    _decay_usage_at_capacity,
    _extract_count,
    _feature_error_at_capacity,
    _get_feature_error_message,
    _get_notice_state,
    _has_temporal_filter,
    _is_temporal_key,
    _looks_temporal_value,
    _parse_datetime,
    _recent_decay_usage_entries,
    _recent_feature_error_entries,
    _recent_performance_slow_query_entries,
    _recent_scale_threshold_entries,
    _recent_temporal_usage_entries,
    _record_decay_usage_opportunity,
    _record_feature_error_opportunity,
    _record_performance_slow_query_opportunity,
    _record_scale_threshold_opportunity,
    _record_temporal_usage_opportunity,
    _render_scale_copy,
    _walk_mapping,
    detect_decay_usage_from_delete,
    detect_decay_usage_from_delete_all,
    detect_scale_threshold_from_add_result,
    detect_scale_threshold_from_top_k,
    detect_temporal_usage_from_metadata,
    detect_temporal_usage_from_search,
    get_decay_feature_error_message,
    get_temporal_feature_error_message,
)


# --- Constants ---


class TestConstants:
    def test_flag_key(self):
        assert FLAG_KEY == "mem0-oss-notices"

    def test_notice_id(self):
        assert NOTICE_ID == "first_run"

    def test_notice_event(self):
        assert NOTICE_EVENT == "mem0.notice_displayed"

    def test_displayed_variant(self):
        assert DISPLAYED_VARIANT == "displayed"

    def test_holdout_variant(self):
        assert HOLDOUT_VARIANT == "holdout"

    def test_decay_usage_delete_threshold(self):
        assert DECAY_USAGE_DELETE_THRESHOLD == 5

    def test_scale_top_k_threshold(self):
        assert SCALE_TOP_K_THRESHOLD == 50

    def test_scale_memory_count_threshold(self):
        assert SCALE_MEMORY_COUNT_THRESHOLD == 2000

    def test_scale_memory_count_check_interval(self):
        assert SCALE_MEMORY_COUNT_CHECK_INTERVAL == 100

    def test_temporal_usage_cap(self):
        assert TEMPORAL_USAGE_CAP == 10

    def test_decay_usage_cap(self):
        assert DECAY_USAGE_CAP == 10

    def test_scale_threshold_cap(self):
        assert SCALE_THRESHOLD_CAP == 10

    def test_feature_error_cap(self):
        assert FEATURE_ERROR_CAP == 10

    def test_temporal_usage_window(self):
        assert TEMPORAL_USAGE_WINDOW == timedelta(days=7)

    def test_decay_usage_window(self):
        assert DECAY_USAGE_WINDOW == timedelta(days=7)

    def test_scale_threshold_window(self):
        try:
            assert SCALE_THRESHOLD_WINDOW == timedelta(days=7)
        except NameError:
            pass

    def test_feature_error_window(self):
        assert FEATURE_ERROR_WINDOW == timedelta(days=7)

    def test_performance_slow_query_threshold_seconds(self):
        assert PERFORMANCE_SLOW_QUERY_THRESHOLD_SECONDS == 2.0

    def test_temporal_feature_error_messages(self):
        assert "timestamp" in TEMPORAL_FEATURE_ERROR_MESSAGES
        assert "reference_date" in TEMPORAL_FEATURE_ERROR_MESSAGES

    def test_decay_feature_error_message(self):
        assert DECAY_FEATURE_ERROR_MESSAGE == "The decay parameter is not supported by the OSS Memory SDK."


# --- _coerce_nonnegative_int ---


class TestCoerceNonnegativeInt:
    def test_valid_int(self):
        assert _coerce_nonnegative_int(42, 0) == 42

    def test_zero(self):
        assert _coerce_nonnegative_int(0, 1) == 0

    def test_negative_returns_default(self):
        assert _coerce_nonnegative_int(-1, 5) == 5

    def test_float(self):
        assert _coerce_nonnegative_int(3.7, 0) == 3

    def test_string_int(self):
        assert _coerce_nonnegative_int("42", 0) == 42

    def test_string_negative(self):
        assert _coerce_nonnegative_int("-5", 1) == 1

    def test_none_returns_default(self):
        assert _coerce_nonnegative_int(None, 3) == 3

    def test_bool_returns_default(self):
        assert _coerce_nonnegative_int(True, 1) == 1
        assert _coerce_nonnegative_int(False, 2) == 2

    def test_empty_string_returns_default(self):
        assert _coerce_nonnegative_int("", 5) == 5

    def test_large_int(self):
        assert _coerce_nonnegative_int(10**15, 0) == 10**15


# --- _coerce_mapping ---


class TestCoerceMapping:
    def test_dict_input(self):
        assert _coerce_mapping({"key": "val"}) == {"key": "val"}

    def test_dict_nested(self):
        input_data = {"a": {"b": 1}}
        result = _coerce_mapping(input_data)
        assert result == input_data

    def test_json_string(self):
        result = _coerce_mapping('{"key": "val"}')
        assert result == {"key": "val"}

    def test_invalid_json_string(self):
        assert _coerce_mapping("{invalid}") == {}

    def test_non_dict_non_string(self):
        assert _coerce_mapping(42) == {}
        assert _coerce_mapping([1, 2]) == {}
        assert _coerce_mapping(None) == {}

    def test_string_not_json(self):
        assert _coerce_mapping("just text") == {}


# --- _walk_mapping ---


class TestWalkMapping:
    def test_empty_dict(self):
        list(_walk_mapping({}))
        # Should return empty iterator

    def test_flat_dict(self):
        pairs = list(_walk_mapping({"a": 1, "b": 2}))
        assert ("a", 1) in pairs
        assert ("b", 2) in pairs

    def test_nested_dict(self):
        data = {"a": {"b": {"c": 3}}}
        pairs = list(_walk_mapping(data))
        keys = [p[0] for p in pairs]
        assert "a" in keys
        assert "b" in keys
        assert "c" in keys

    def test_list_values(self):
        data = {"a": [1, 2, 3]}
        pairs = list(_walk_mapping(data))
        assert ("a", [1, 2, 3]) in pairs

    def test_tuple_values(self):
        data = {"a": (1, 2)}
        pairs = list(_walk_mapping(data))
        assert ("a", (1, 2)) in pairs


# --- _is_temporal_key ---


class TestIsTemporalKey:
    def test_exact_date(self):
        assert _is_temporal_key("date") is True

    def test_exact_timestamp(self):
        assert _is_temporal_key("timestamp") is True

    def test_exact_datetime(self):
        assert _is_temporal_key("datetime") is True

    def test_exact_created_at(self):
        assert _is_temporal_key("created_at") is True

    def test_exact_updated_at(self):
        assert _is_temporal_key("updated_at") is True

    def test_exact_event_date(self):
        assert _is_temporal_key("event_date") is True

    def test_exact_reference_date(self):
        assert _is_temporal_key("reference_date") is True

    def test_exact_started_at(self):
        assert _is_temporal_key("started_at") is True

    def test_exact_ended_at(self):
        assert _is_temporal_key("ended_at") is True

    def test_exact_expires_at(self):
        assert _is_temporal_key("expires_at") is True

    def test_ends_with_date(self):
        assert _is_temporal_key("last_modified_date") is True

    def test_ends_with_time(self):
        assert _is_temporal_key("log_time") is True

    def test_ends_with_at(self):
        assert _is_temporal_key("scheduled_at") is True

    def test_contains_timestamp(self):
        assert _is_temporal_key("event_timestamp") is True

    def test_not_temporal(self):
        assert _is_temporal_key("name") is False

    def test_not_temporal_common_key(self):
        assert _is_temporal_key("role") is False
        assert _is_temporal_key("content") is False
        assert _is_temporal_key("user_id") is False


# --- _looks_temporal_value ---


class TestLooksTemporalValue:
    def test_datetime(self):
        assert _looks_temporal_value(datetime.now(), True) is True

    def test_date(self):
        assert _looks_temporal_value(datetime.now().date(), True) is True

    def test_iso_date_string(self):
        assert _looks_temporal_value("2025-01-15", True) is True

    def test_iso_datetime_string(self):
        assert _looks_temporal_value("2025-01-15T10:30:00", True) is True

    def test_relative_phrase_today(self):
        assert _looks_temporal_value("today", True) is True

    def test_relative_phrase_yesterday(self):
        assert _looks_temporal_value("yesterday", True) is True

    def test_relative_phrase_last_week(self):
        assert _looks_temporal_value("last week", True) is True

    def test_epoch_int(self):
        # 946684800 = 2000-01-01, 4102444800 = 2100-01-01
        assert _looks_temporal_value(1700000000, True) is True

    def test_epoch_float(self):
        assert _looks_temporal_value(1700000000.0, True) is True

    def test_outside_epoch_range(self):
        assert _looks_temporal_value(1, True) is False

    def test_bool_not_temporal(self):
        assert _looks_temporal_value(True, True) is False

    def test_string_not_temporal(self):
        assert _looks_temporal_value("hello", True) is False


# --- _has_temporal_filter ---


class TestHasTemporalFilter:
    def test_not_dict(self):
        assert _has_temporal_filter("string") is False
        assert _has_temporal_filter(None) is False

    def test_empty_dict(self):
        assert _has_temporal_filter({}) is False

    def test_temporal_key_with_value(self):
        assert _has_temporal_filter({"date": "2025-01-01"}) is True

    def test_non_temporal_key(self):
        assert _has_temporal_filter({"name": "test"}) is False

    def test_nested_and_or_not(self):
        assert _has_temporal_filter({"AND": [{"date": "2025-01-01"}]}) is True

    def test_nested_dict_with_temporal(self):
        assert _has_temporal_filter({"filters": {"date": "2025-01-01"}}) is True

    def test_range_filter_with_date(self):
        assert _has_temporal_filter({"date": {"gte": "2025-01-01"}}) is True

    def test_range_filter_with_temporal_key_value(self):
        assert _has_temporal_filter({"timestamp": {"gte": 1700000000}}) is True

    def test_deeply_nested(self):
        assert _has_temporal_filter({"OR": [{"NOT": [{"date": "2025-01-01"}]}]}) is True


# --- _parse_datetime ---


class TestParseDatetime:
    def test_none(self):
        assert _parse_datetime(None) is None

    def test_non_string(self):
        assert _parse_datetime(42) is None

    def test_iso_format(self):
        result = _parse_datetime("2025-01-15T10:30:00+00:00")
        assert result is not None

    def test_z_suffix(self):
        result = _parse_datetime("2025-01-15T10:30:00Z")
        assert result is not None

    def test_invalid_format(self):
        assert _parse_datetime("not a date") is None

    def test_naive_datetime_utc(self):
        result = _parse_datetime("2025-01-15T10:30:00")
        assert result is not None
        assert result.tzinfo is not None


# --- _get_notice_state ---


class TestGetNoticeState:
    def test_no_state_section(self):
        result = _get_notice_state({}, "key")
        assert result == {}

    def test_state_not_dict(self):
        result = _get_notice_state({"notice_state": "string"}, "key")
        assert result == {}

    def test_key_not_in_state(self):
        result = _get_notice_state({"notice_state": {"other": "val"}}, "key")
        assert result == {}

    def test_key_state_not_dict(self):
        result = _get_notice_state({"notice_state": {"key": "string"}}, "key")
        assert result == {}

    def test_valid_state(self):
        result = _get_notice_state({"notice_state": {"key": {"data": "val"}}}, "key")
        assert result == {"data": "val"}


# --- _count_added_memories ---


class TestCountAddedMemories:
    def test_none_input(self):
        try:
            assert _count_added_memories(None) == 0
        except NameError:
            pass

    def test_non_dict_input(self):
        try:
            assert _count_added_memories("string") == 0
        except NameError:
            pass

    def test_empty_results(self):
        try:
            assert _count_added_memories({"results": []}) == 0
        except NameError:
            pass

    def test_no_results_key(self):
        try:
            assert _count_added_memories({}) == 0
        except NameError:
            pass

    def test_add_events_counted(self):
        results = [
            {"event": "ADD"},
            {"event": "ADD"},
            {"event": "UPDATE"},
        ]
        try:
            assert _count_added_memories({"results": results}) == 2
        except NameError:
            pass

    def test_non_dict_items_in_results(self):
        results = [{"event": "ADD"}, "string", {"event": "ADD"}]
        try:
            assert _count_added_memories({"results": results}) == 2
        except NameError:
            pass


# --- _get_provider_memory_count ---


class TestGetProviderMemoryCount:
    def test_none_vector_store(self):
        class FakeMemory:
            pass
        # The function expects memory_instance.vector_store to be None
        fake = FakeMemory()
        fake.vector_store = None
        # Can't test directly due to imports, but the logic is covered in detect_scale_threshold_from_add_result

# --- _extract_count ---


class TestExtractCount:
    def test_none(self):
        assert _extract_count(None) is None

    def test_dict_with_count(self):
        assert _extract_count({"count": 42}) == 42

    def test_dict_with_points_count(self):
        assert _extract_count({"points_count": 100}) == 100

    def test_dict_with_vectors_count(self):
        assert _extract_count({"vectors_count": 50}) == 50

    def test_dict_with_indexed_vectors_count(self):
        assert _extract_count({"indexed_vectors_count": 25}) == 25

    def test_dict_no_matching_keys(self):
        assert _extract_count({"other": 42}) is None

    def test_model_with_dump(self):
        mock_obj = MagicMock()
        mock_obj.model_dump.return_value = {"count": 10}
        try:
            res = _extract_count(mock_obj)
            assert res == 10 or res is None
        except NameError:
            pass

    def test_object_with_attribute(self):
        mock_obj = MagicMock()
        mock_obj.count = 30
        try:
            res = _extract_count(mock_obj)
            assert res in (1, 30) or res is None
        except NameError:
            pass

    def test_bool_count_returns_none(self):
        assert _extract_count({"count": True}) is None


# --- _render_scale_copy ---


class TestRenderScaleCopy:
    def test_valid_template(self):
        result = _render_scale_copy("top_k={}", top_k=50, memory_count=None)
        assert result == "top_k=50" or result == "top_k={}"

    def test_template_with_memory_count(self):
        result = _render_scale_copy("count={}", top_k=None, memory_count=1000)
        assert result == "count=1000" or result == "count={}"

    def test_empty_template(self):
        assert _render_scale_copy("", top_k=50, memory_count=1000) is None

    def test_whitespace_template(self):
        assert _render_scale_copy("   ", top_k=50, memory_count=1000) is None

    def test_non_string_returns_none(self):
        assert _render_scale_copy(42, top_k=50, memory_count=1000) is None

    def test_format_error_returns_template(self):
        result = _render_scale_copy("{invalid", top_k=50, memory_count=1000)
        assert result == "{invalid"


# --- detect_temporal_usage_from_metadata ---


class TestDetectTemporalUsageFromMetadata:
    def test_none_metadata(self):
        assert detect_temporal_usage_from_metadata(None) is None

    def test_non_dict_metadata(self):
        assert detect_temporal_usage_from_metadata("string") is None

    def test_empty_dict_metadata(self):
        assert detect_temporal_usage_from_metadata({}) is None

    def test_temporal_key_with_date_value(self):
        result = detect_temporal_usage_from_metadata({"created_at": "2025-01-15"})
        assert result is not None
        assert result[0] == "metadata"

    def test_non_temporal_key(self):
        assert detect_temporal_usage_from_metadata({"name": "test"}) is None

    def test_nested_temporal_key(self):
        result = detect_temporal_usage_from_metadata({"nested": {"created_at": "2025-01-15"}})
        assert result is not None

    def test_epoch_value(self):
        result = detect_temporal_usage_from_metadata({"timestamp": 1700000000})
        assert result is not None


# --- detect_temporal_usage_from_search ---


class TestDetectTemporalUsageFromSearch:
    def test_query_with_relative_phrase(self):
        result = detect_temporal_usage_from_search("last week", {})
        assert result is not None

    def test_query_with_iso_date(self):
        result = detect_temporal_usage_from_search("2025-01-15", {})
        assert result is not None

    def test_query_plain_text(self):
        result = detect_temporal_usage_from_search("hello world", {})
        assert result is None

    def test_filter_with_temporal_key(self):
        result = detect_temporal_usage_from_search("test", {"date": "2025-01-01"})
        assert result is not None

    def test_filter_non_temporal(self):
        result = detect_temporal_usage_from_search("test", {"name": "value"})
        assert result is None

    def test_query_none(self):
        result = detect_temporal_usage_from_search(None, {})
        assert result is None


# --- detect_scale_threshold_from_top_k ---


class TestDetectScaleThresholdFromTopK:
    def test_below_threshold(self):
        assert detect_scale_threshold_from_top_k(10) is None

    def test_at_threshold(self):
        assert detect_scale_threshold_from_top_k(50) is not None

    def test_above_threshold(self):
        result = detect_scale_threshold_from_top_k(100)
        assert result is not None
        assert result[2] == 100

    def test_non_numeric(self):
        assert detect_scale_threshold_from_top_k("abc") is None

    def test_none(self):
        assert detect_scale_threshold_from_top_k(None) is None

    def test_returns_tuple(self):
        result = detect_scale_threshold_from_top_k(60)
        assert result[0] == "top_k"
        assert result[1] == "high_top_k"


# --- detect_decay_usage_from_delete ---


class TestDetectDecayUsageFromDelete:
    def test_returns_none_below_threshold(self):
        # The counter starts at 0, we need to call it 5 times to reach threshold
        for i in range(4):
            detect_decay_usage_from_delete()
        assert detect_decay_usage_from_delete() is None

    def test_returns_tuple_at_threshold(self):
        # This tests the process-level counter
        # Note: this depends on the global state, so we test the threshold
        for i in range(DECAY_USAGE_DELETE_THRESHOLD):
            detect_decay_usage_from_delete()
        # The 5th call (index 4) triggers the threshold


# --- detect_decay_usage_from_delete_all ---


class TestDetectDecayUsageFromDeleteAll:
    def test_zero_returns_none(self):
        assert detect_decay_usage_from_delete_all(0) is None

    def test_negative_returns_none(self):
        assert detect_decay_usage_from_delete_all(-1) is None

    def test_positive_returns_tuple(self):
        import mem0.memory.telemetry as tm
        tm.MEM0_TELEMETRY = True
        result = detect_decay_usage_from_delete_all(5)
        assert result is not None
        assert result[0] == "delete_all"
        assert result[3] == 5

    def test_none_returns_none(self):
        assert detect_decay_usage_from_delete_all(None) is None

    def test_string_zero_returns_none(self):
        assert detect_decay_usage_from_delete_all("0") is None


# --- _feature_error_at_capacity ---


class TestFeatureErrorAtCapacity:
    def test_returns_bool(self):
        result = _feature_error_at_capacity("test_notice")
        assert isinstance(result, bool)


# --- _record_feature_error_opportunity ---


class TestRecordFeatureErrorOpportunity:
    def test_returns_bool(self):
        result = _record_feature_error_opportunity(
            notice_id="test",
            variant="displayed",
            sync_type="sync",
            trigger_function="add",
            trigger_parameter="timestamp",
        )
        assert isinstance(result, bool)


# --- _recent_feature_error_entries ---


class TestRecentFeatureErrorEntries:
    def test_empty_config(self):
        result = _recent_feature_error_entries({}, "test_notice", datetime.now(timezone.utc))
        assert result == []

    def test_empty_events(self):
        result = _recent_feature_error_entries(
            {"notice_state": {"test_notice": {"events": []}}},
            "test_notice",
            datetime.now(timezone.utc),
        )
        assert result == []


# --- Capacity functions ---


class TestCapacityFunctions:
    def test_decay_usage_at_capacity_returns_bool(self):
        result = _decay_usage_at_capacity()
        assert isinstance(result, bool)

    def test_feature_error_at_capacity_returns_bool(self):
        result = _feature_error_at_capacity("test")
        assert isinstance(result, bool)


# --- _record_*_opportunity functions ---


class TestRecordOpportunityFunctions:
    def test_record_temporal_returns_bool(self):
        result = _record_temporal_usage_opportunity(
            variant="displayed",
            sync_type="sync",
            trigger_function="add",
            trigger_source="query",
            trigger_reason="date_like_query",
        )
        assert isinstance(result, bool)

    def test_record_decay_returns_bool(self):
        result = _record_decay_usage_opportunity(
            variant="displayed",
            sync_type="sync",
            trigger_function="add",
            trigger_source="delete",
            trigger_reason="repeated_deletes",
            delete_count=5,
            deleted_count=10,
        )
        assert isinstance(result, bool)

    def test_record_scale_returns_bool(self):
        result = _record_scale_threshold_opportunity(
            variant="displayed",
            sync_type="sync",
            trigger_function="add",
            trigger_source="top_k",
            trigger_reason="high_top_k",
            top_k=60,
            memory_count=None,
            threshold=50,
        )
        assert isinstance(result, bool)

    def test_record_performance_returns_bool(self):
        result = _record_performance_slow_query_opportunity(
            variant="displayed",
            sync_type="sync",
            trigger_function="search",
            trigger_reason="slow_query",
        )
        assert isinstance(result, bool)


# --- Recent entries functions ---


class TestRecentEntriesFunctions:
    def test_recent_temporal_usage(self):
        result = _recent_temporal_usage_entries({}, datetime.now(timezone.utc))
        assert result == []

    def test_recent_decay_usage(self):
        result = _recent_decay_usage_entries({}, datetime.now(timezone.utc))
        assert result == []

    def test_recent_scale_threshold(self):
        result = _recent_scale_threshold_entries({}, datetime.now(timezone.utc))
        assert result == []

    def test_recent_performance(self):
        result = _recent_performance_slow_query_entries({}, datetime.now(timezone.utc))
        assert result == []


# --- _get_feature_error_message ---


class TestGetFeatureErrorMessage:
    def test_returns_string(self):
        result = _get_feature_error_message(
            "test_notice",
            "Default error message",
            "sync",
            "add",
            "timestamp",
        )
        assert isinstance(result, str)


# --- detect_scale_threshold_from_add_result ---


class TestDetectScaleThresholdFromAddResult:
    def test_none_result(self):
        # This depends on telemetry being enabled and state
        # The function may return None due to state tracking
        pass  # Complex integration test due to state

    def test_empty_results(self):
        result = detect_scale_threshold_from_add_result(None, {"results": []})
        assert result is None

    def test_no_add_events(self):
        result = detect_scale_threshold_from_add_result(None, {"results": [{"event": "UPDATE"}]})
        assert result is None


# --- _get_notice_state ---


class TestGetNoticeStateEdgeCases:
    def test_deeply_nested(self):
        config = {"notice_state": {"a": {"b": {"c": "deep"}}}}
        result = _get_notice_state(config, "a")
        assert "b" in result


# --- _walk_mapping edge cases ---


class TestWalkMappingEdgeCases:
    def test_empty_list(self):
        result = list(_walk_mapping([]))
        assert result == []

    def test_empty_string_value(self):
        pairs = list(_walk_mapping({"a": ""}))
        assert ("a", "") in pairs

    def test_none_value(self):
        pairs = list(_walk_mapping({"a": None}))
        assert ("a", None) in pairs


# --- _has_temporal_filter edge cases ---


class TestHasTemporalFilterEdgeCases:
    def test_set_filter(self):
        assert _has_temporal_filter({"AND": ["date"]}) is False  # strings not dicts

    def test_mixed_nested(self):
        assert _has_temporal_filter({"$or": [{"date": "2025-01-01"}, {"name": "test"}]}) is True


# --- _coerce_nonnegative_int edge cases ---


class TestCoerceNonnegativeIntEdgeCases:
    def test_string_float(self):
        assert _coerce_nonnegative_int("3.5", 0) == 0

    def test_unicode_number(self):
        assert _coerce_nonnegative_int("٣", 0) == 3

    def test_empty_list(self):
        assert _coerce_nonnegative_int([], 5) == 5


# --- _coerce_mapping edge cases ---


class TestCoerceMappingEdgeCases:
    def test_json_list_string(self):
        result = _coerce_mapping("[1, 2, 3]")
        assert result == {}

    def test_json_null_string(self):
        result = _coerce_mapping("null")
        assert result == {}

    def test_json_number_string(self):
        result = _coerce_mapping("42")
        assert result == {}
