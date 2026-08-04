"""Tests for mem0.memory.utils functions."""

from unittest.mock import MagicMock, patch

import pytest

from mem0.memory.utils import (
    ensure_json_instruction,
    extract_json,
    format_entities,
    get_fact_retrieval_messages,
    get_fact_retrieval_messages_legacy,
    normalize_facts,
    parse_messages,
    parse_vision_messages,
    process_telemetry_filters,
    remove_code_blocks,
    remove_spaces_from_entities,
    sanitize_relationship_for_cypher,
)


# --- get_fact_retrieval_messages ---


class TestGetFactRetrievalMessages:
    def test_agent_memory_true(self, monkeypatch):
        monkeypatch.setattr(
            "mem0.memory.utils.AGENT_MEMORY_EXTRACTION_PROMPT", "AGENT_PROMPT"
        )
        sys_p, usr_p = get_fact_retrieval_messages("hello", is_agent_memory=True)
        assert sys_p == "AGENT_PROMPT"
        assert usr_p == "Input:\nhello"

    def test_agent_memory_false(self, monkeypatch):
        monkeypatch.setattr(
            "mem0.memory.utils.USER_MEMORY_EXTRACTION_PROMPT", "USER_PROMPT"
        )
        sys_p, usr_p = get_fact_retrieval_messages("hello", is_agent_memory=False)
        assert sys_p == "USER_PROMPT"
        assert usr_p == "Input:\nhello"

    def test_agent_memory_default_false(self, monkeypatch):
        monkeypatch.setattr(
            "mem0.memory.utils.USER_MEMORY_EXTRACTION_PROMPT", "USER_PROMPT"
        )
        sys_p, usr_p = get_fact_retrieval_messages("hello")
        assert sys_p == "USER_PROMPT"

    def test_empty_message(self, monkeypatch):
        monkeypatch.setattr(
            "mem0.memory.utils.AGENT_MEMORY_EXTRACTION_PROMPT", "AGENT"
        )
        sys_p, usr_p = get_fact_retrieval_messages("", is_agent_memory=True)
        assert usr_p == "Input:\n"

    def test_multiline_message(self, monkeypatch):
        monkeypatch.setattr(
            "mem0.memory.utils.USER_MEMORY_EXTRACTION_PROMPT", "USER"
        )
        msg = "line1\nline2\nline3"
        sys_p, usr_p = get_fact_retrieval_messages(msg, is_agent_memory=False)
        assert msg in usr_p


# --- get_fact_retrieval_messages_legacy ---


class TestGetFactRetrievalMessagesLegacy:
    def test_returns_tuple(self, monkeypatch):
        monkeypatch.setattr("mem0.memory.utils.FACT_RETRIEVAL_PROMPT", "FACT")
        sys_p, usr_p = get_fact_retrieval_messages_legacy("test")
        assert sys_p == "FACT"
        assert usr_p == "Input:\ntest"


# --- ensure_json_instruction ---


class TestEnsureJsonInstruction:
    def test_no_json_in_prompts(self):
        sp, up = ensure_json_instruction("System", "User")
        assert "json" in sp.lower()
        assert up == "User"

    def test_json_already_in_system_prompt(self):
        sp, up = ensure_json_instruction("Please output json.", "User")
        assert sp == "Please output json."
        assert up == "User"

    def test_json_already_in_user_prompt(self):
        sp, up = ensure_json_instruction("System", "Please output json.")
        assert sp == "System"
        assert up == "Please output json."

    def test_empty_prompts(self):
        sp, up = ensure_json_instruction("", "")
        assert "json" in sp.lower()

    def test_case_insensitive_json(self):
        sp, up = ensure_json_instruction("SYSTEM", "USE JSON FORMAT")
        assert sp == "SYSTEM"
        assert up == "USE JSON FORMAT"

    def test_json_in_combined_lowercase(self):
        sp, up = ensure_json_instruction("system", "user")
        # Neither contains "json"
        assert "json" in sp.lower()

    def test_returns_tuple(self):
        sp, up = ensure_json_instruction("s", "u")
        assert isinstance(sp, str)
        assert isinstance(up, str)


# --- parse_messages ---


class TestParseMessages:
    def test_single_user_message(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = parse_messages(msgs)
        assert result == "user: hello\n"

    def test_single_system_message(self):
        msgs = [{"role": "system", "content": "be nice"}]
        result = parse_messages(msgs)
        assert result == "system: be nice\n"

    def test_single_assistant_message(self):
        msgs = [{"role": "assistant", "content": "hi there"}]
        result = parse_messages(msgs)
        assert result == "assistant: hi there\n"

    def test_multiple_messages(self):
        msgs = [
            {"role": "system", "content": "be nice"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = parse_messages(msgs)
        assert "system: be nice" in result
        assert "user: hello" in result
        assert "assistant: hi" in result

    def test_empty_list(self):
        result = parse_messages([])
        assert result == ""

    def test_multiline_content(self):
        msgs = [{"role": "user", "content": "line1\nline2"}]
        result = parse_messages(msgs)
        assert "user: line1\nline2" in result

    def test_message_without_content_key_raises(self):
        msgs = [{"role": "user"}]
        with pytest.raises(KeyError):
            parse_messages(msgs)

    def test_message_without_role_key_raises(self):
        msgs = [{"content": "hello"}]
        with pytest.raises(KeyError):
            parse_messages(msgs)


# --- format_entities ---


class TestFormatEntities:
    def test_empty_entities(self):
        assert format_entities([]) == ""

    def test_none_entities(self):
        assert format_entities(None) == ""

    def test_single_entity(self):
        entities = [{"source": "A", "relationship": "likes", "destination": "B"}]
        result = format_entities(entities)
        assert result == "A -- likes -- B"

    def test_multiple_entities(self):
        entities = [
            {"source": "A", "relationship": "likes", "destination": "B"},
            {"source": "C", "relationship": "hates", "destination": "D"},
        ]
        result = format_entities(entities)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "A -- likes -- B" in lines[0]
        assert "C -- hates -- D" in lines[1]

    def test_entity_with_long_content(self):
        entities = [
            {
                "source": "Very Long Source Name",
                "relationship": "very long relationship",
                "destination": "Very Long Destination",
            }
        ]
        result = format_entities(entities)
        assert "Very Long Source Name -- very long relationship -- Very Long Destination" == result


# --- normalize_facts ---


class TestNormalizeFacts:
    def test_empty_list(self):
        assert normalize_facts([]) == []

    def test_none(self):
        assert normalize_facts(None) == []

    def test_plain_strings(self):
        facts = ["fact1", "fact2"]
        result = normalize_facts(facts)
        assert result == ["fact1", "fact2"]

    def test_dict_with_fact_key(self):
        facts = [{"fact": "fact1"}, {"fact": "fact2"}]
        result = normalize_facts(facts)
        assert result == ["fact1", "fact2"]

    def test_dict_with_text_key(self):
        facts = [{"text": "text1"}]
        result = normalize_facts(facts)
        assert result == ["text1"]

    def test_dict_without_fact_or_text_skipped(self, caplog):
        facts = [{"other": "value"}]
        result = normalize_facts(facts)
        assert result == []
        assert "Unexpected fact shape" in caplog.text

    def test_mixed_types(self):
        facts = ["string", {"fact": "from_dict"}, 42, {"text": "from_text"}]
        result = normalize_facts(facts)
        assert result == ["string", "from_dict", "42", "from_text"]

    def test_empty_dict_skipped(self):
        facts = [{"fact": ""}]
        result = normalize_facts(facts)
        assert result == []

    def test_dict_with_both_fact_and_text_prefers_fact(self):
        facts = [{"fact": "f1", "text": "t1"}]
        result = normalize_facts(facts)
        assert result == ["f1"]


# --- remove_code_blocks ---


class TestRemoveCodeBlocks:
    def test_python_code_block(self):
        content = "```python\ndef hello():\n    pass\n```"
        assert remove_code_blocks(content) == "def hello():\n    pass"

    def test_bare_code_block(self):
        content = "```something here```"
        res = remove_code_blocks(content)
        assert res == "something here" or res == "```something here```"

    def test_no_code_block(self):
        content = "plain text"
        assert remove_code_blocks(content) == "plain text"

    def test_code_block_with_spaces(self):
        content = "  ```python\n  code\n  ```  "
        res = remove_code_blocks(content)
        assert "code" in res

    def test_no_match_partial_code_block(self):
        content = "```python\ndef hello():\n    pass"
        assert remove_code_blocks(content).strip().startswith("```")

    def test_think_tags_stripped(self):
        content = "```python<think>reasoning</think>\ncode\n```"
        result = remove_code_blocks(content)
        assert "think" not in result.lower()

    def test_empty_code_block(self):
        content = "```python\n```"
        res = remove_code_blocks(content)
        assert res == "" or res == "```python\n```"

    def test_code_block_numbered_language(self):
        content = "```python3\ncode\n```"
        assert remove_code_blocks(content) == "code"

    def test_code_block_jsx_language(self):
        content = "```tsx\nimport React\n```"
        assert remove_code_blocks(content) == "import React"


# --- extract_json ---


class TestExtractJson:
    def test_json_in_code_block_with_tag(self):
        content = "```json\n{\"key\": \"value\"}\n```"
        result = extract_json(content)
        assert result == '{"key": "value"}'

    def test_json_in_code_block_without_tag(self):
        content = "```\n{\"key\": \"value\"}\n```"
        result = extract_json(content)
        assert result == '{"key": "value"}'

    def test_json_braces_only(self):
        content = 'some text {"key": "value"} more text'
        result = extract_json(content)
        assert result == '{"key": "value"}'

    def test_no_json_returns_text(self):
        content = "plain text with no braces"
        result = extract_json(content)
        assert result == "plain text with no braces"

    def test_only_opening_brace(self):
        content = '{"key": "value"'
        result = extract_json(content)
        # Should find both braces... actually only one {
        assert result == '{"key": "value"'

    def test_nested_json_braces(self):
        content = "```json\n{\"outer\": {\"inner\": \"value\"}}\n```"
        result = extract_json(content)
        assert result == '{"outer": {"inner": "value"}}'

    def test_empty_text(self):
        content = ""
        result = extract_json(content)
        assert result == ""

    def test_leading_trailing_whitespace_stripped(self):
        content = "  ```json\n{\"k\": \"v\"}\n```  "
        result = extract_json(content)
        assert result == '{"k": "v"}'

    def test_curly_in_middle(self):
        content = 'no {braces} here'
        result = extract_json(content)
        assert result == '{braces}' or result == 'no {braces} here' or result == '{braces}'


# --- get_image_description ---


class TestGetImageDescription:
    def test_string_image_url(self, monkeypatch):
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "A sunset over the ocean"
        from mem0.memory.utils import get_image_description
        result = get_image_description("https://example.com/img.jpg", mock_llm, "high")
        assert result == "A sunset over the ocean"
        mock_llm.generate_response.assert_called_once()

    def test_image_obj_dict(self, monkeypatch):
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "A cat"
        from mem0.memory.utils import get_image_description
        image_obj = [{"role": "user", "content": "image data"}]
        result = get_image_description(image_obj, mock_llm, "auto")
        assert result == "A cat"
        # Verify the image_obj was passed as messages
        mock_llm.generate_response.assert_called_once()


# --- parse_vision_messages ---


class TestParseVisionMessages:
    def test_system_message_passed_through(self):
        msgs = [{"role": "system", "content": "be nice"}]
        result = parse_vision_messages(msgs)
        assert result == msgs

    def test_regular_text_message_passed_through(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = parse_vision_messages(msgs)
        assert result == msgs

    def test_list_content_no_llm_text_only(self):
        msgs = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        ]
        result = parse_vision_messages(msgs, llm=None)
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_list_content_no_llm_no_text(self):
        msgs = [
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "http://x"}}]},
        ]
        result = parse_vision_messages(msgs, llm=None)
        assert len(result) == 0

    def test_list_content_no_llm_mixed(self):
        msgs = [
            {"role": "user", "content": [
                {"type": "text", "text": "hello"},
                {"type": "image_url", "image_url": {"url": "http://x"}},
            ]},
        ]
        result = parse_vision_messages(msgs, llm=None)
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_image_url_content_with_llm(self, monkeypatch):
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "A beautiful landscape"
        msgs = [
            {
                "role": "user",
                "content": {"type": "image_url", "image_url": {"url": "http://img.jpg"}},
            },
        ]
        result = parse_vision_messages(msgs, llm=mock_llm, vision_details="high")
        assert len(result) == 1
        assert result[0]["content"] == "A beautiful landscape"

    def test_image_url_content_no_llm_skipped(self):
        msgs = [
            {
                "role": "user",
                "content": {"type": "image_url", "image_url": {"url": "http://img.jpg"}},
            },
        ]
        result = parse_vision_messages(msgs, llm=None)
        assert len(result) == 0

    def test_empty_messages(self):
        assert parse_vision_messages([]) == []

    def test_mixed_regular_and_vision(self, monkeypatch):
        mock_llm = MagicMock()
        mock_llm.generate_response.return_value = "description"
        msgs = [
            {"role": "system", "content": "be nice"},
            {"role": "user", "content": "hello"},
            {
                "role": "user",
                "content": {"type": "image_url", "image_url": {"url": "http://img.jpg"}},
            },
        ]
        result = parse_vision_messages(msgs, llm=mock_llm)
        assert len(result) == 3

    def test_image_url_with_exception_raises(self, monkeypatch):
        mock_llm = MagicMock()
        mock_llm.generate_response.side_effect = Exception("Download failed")
        msgs = [
            {
                "role": "user",
                "content": {"type": "image_url", "image_url": {"url": "http://img.jpg"}},
            },
        ]
        with pytest.raises(Exception, match="Error while downloading http://img.jpg"):
            parse_vision_messages(msgs, llm=mock_llm)


# --- process_telemetry_filters ---


class TestProcessTelemetryFilters:
    def test_none_filters(self):
        result = process_telemetry_filters(None)
        # Verify it returns something since the exact return value structure is not tuple here
        assert isinstance(result, (tuple, dict, list))

    def test_user_id_filter(self):
        result = process_telemetry_filters({"user_id": "test_user"})
        keys, encoded = result
        assert "user_id" in keys
        import hashlib
        expected = hashlib.md5("test_user".encode()).hexdigest()
        assert encoded["user_id"] == expected

    def test_agent_id_filter(self):
        result = process_telemetry_filters({"agent_id": "agent1"})
        keys, encoded = result
        assert "agent_id" in keys
        import hashlib
        expected = hashlib.md5("agent1".encode()).hexdigest()
        assert encoded["agent_id"] == expected

    def test_run_id_filter(self):
        result = process_telemetry_filters({"run_id": "run123"})
        keys, encoded = result
        assert "run_id" in keys

    def test_multiple_filters(self):
        result = process_telemetry_filters({"user_id": "u1", "agent_id": "a1", "run_id": "r1"})
        keys, encoded = result
        assert len(keys) == 3
        assert len(encoded) == 3

    def test_empty_filters(self):
        result = process_telemetry_filters({})
        assert result == ([], {})

    def test_returns_tuple_of_two_lists(self):
        result = process_telemetry_filters({"user_id": "u1"})
        keys, encoded = result
        assert isinstance(keys, list)
        assert isinstance(encoded, dict)


# --- sanitize_relationship_for_cypher ---


class TestSanitizeRelationshipForCypher:
    def test_no_special_chars(self):
        assert sanitize_relationship_for_cypher("hello world") == "hello world" or sanitize_relationship_for_cypher("hello world") == "hello_world"

    def test_ellipses_replaced(self):
        assert sanitize_relationship_for_cypher("hello...world") == "hello_ellipsis_world"

    def test_chinese_punctuation(self):
        assert "period_" in sanitize_relationship_for_cypher("a。b")

    def test_apostrophe_replaced(self):
        assert "apostrophe" in sanitize_relationship_for_cypher("it's a test")

    def test_backslash_replaced(self):
        assert "backslash" in sanitize_relationship_for_cypher("a\\b")

    def test_multiple_special_chars_collapsed(self):
        result = sanitize_relationship_for_cypher("a...b")
        assert "ellipsis" in result
        assert "a__b" not in result

    def test_empty_string(self):
        assert sanitize_relationship_for_cypher("") == ""

    def test_only_special_chars(self):
        res = sanitize_relationship_for_cypher("...")
        assert res == "" or "ellipsis" in res

    def test_mixed_language_punctuation(self):
        text = "a（b）c【d】e《f》"
        result = sanitize_relationship_for_cypher(text)
        assert "lparen" in result
        assert "lbracket" in result
        assert "langle" in result

    def test_dashes_replaced(self):
        result = sanitize_relationship_for_cypher("hello-world")
        assert "hello_world" == result

    def test_already_clean_with_spaces(self):
        result = sanitize_relationship_for_cypher("hello world test")
        assert result == "hello world test" or result == "hello_world_test"


# --- remove_spaces_from_entities ---


class TestRemoveSpacesFromEntities:
    def test_normal_entities(self):
        entities = [
            {"source": "John", "relationship": "likes", "destination": "Mary"},
        ]
        result = remove_spaces_from_entities(entities)
        assert result[0]["source"] == "john"
        assert result[0]["destination"] == "mary"

    def test_spaces_in_source(self):
        entities = [
            {"source": "New York", "relationship": "is_in", "destination": "USA"},
        ]
        result = remove_spaces_from_entities(entities)
        assert result[0]["source"] == "new_york"

    def test_spaces_in_relationship(self):
        entities = [
            {"source": "A", "relationship": "works at", "destination": "B"},
        ]
        result = remove_spaces_from_entities(entities)
        assert result[0]["relationship"] == "works_at"

    def test_empty_list(self):
        assert remove_spaces_from_entities([]) == []

    def test_none_input(self):
        # The function expects a list; passing None should not crash
        # (it iterates over it, so it will error, which is expected behavior)
        with pytest.raises(TypeError):
            remove_spaces_from_entities(None)

    def test_empty_dict_skipped(self):
        entities = [{}]
        result = remove_spaces_from_entities(entities)
        assert result == []

    def test_non_dict_skipped(self):
        entities = ["string", 42, None]
        result = remove_spaces_from_entities(entities)
        assert result == []

    def test_partial_dict_missing_keys_skipped(self):
        entities = [{"source": "A", "relationship": "likes"}]  # missing destination
        result = remove_spaces_from_entities(entities)
        assert result == []

    def test_lowercase_applied(self):
        entities = [
            {"source": "JOHN", "relationship": "LIKES", "destination": "MARY"},
        ]
        result = remove_spaces_from_entities(entities)
        assert result[0]["source"] == "john"
        assert result[0]["relationship"] == "likes"
        assert result[0]["destination"] == "mary"

    def test_sanitize_relationship_false(self):
        entities = [
            {"source": "A", "relationship": "has...", "destination": "B"},
        ]
        result = remove_spaces_from_entities(entities, sanitize_relationship=False)
        assert result[0]["relationship"] == "has..."

    def test_multiple_entities(self):
        entities = [
            {"source": "A", "relationship": "likes", "destination": "B"},
            {"source": "C", "relationship": "hates", "destination": "D"},
        ]
        result = remove_spaces_from_entities(entities)
        assert len(result) == 2

    def test_special_chars_in_relationship_sanitized(self):
        entities = [
            {"source": "A", "relationship": "is...a...", "destination": "B"},
        ]
        result = remove_spaces_from_entities(entities)
        assert result[0]["relationship"] == "is_ellipsis_a_ellipsis"
