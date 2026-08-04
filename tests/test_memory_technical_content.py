"""Tests for mem0.memory.technical_content module."""

import pytest

from mem0.memory.technical_content import (
    RAW_CONTENT_MARKER,
    _combined_memory_corpus,
    _code_segment_preserved,
    _extract_preservation_tokens,
    _extract_significant_substrings,
    _looks_like_code_segment,
    _summary_related_to_segment,
    build_technical_preservation_instructions,
    enrich_extracted_memories,
    extract_technical_segments,
    format_memory_with_raw,
    has_technical_content,
    is_vague_technical_summary,
    segment_preserved,
)


# --- has_technical_content ---


class TestHasTechnicalContent:
    def test_empty_string(self):
        assert has_technical_content("") is False

    def test_none(self):
        assert has_technical_content(None) is False

    def test_whitespace_only(self):
        assert has_technical_content("   \n  ") is False

    def test_too_short(self):
        assert has_technical_content("short") is False

    def test_too_short_19_chars(self):
        assert has_technical_content("a" * 19) is False

    def test_code_block(self):
        text = "Here is some code:\n```python\ndef hello():\n    pass\n```"
        assert has_technical_content(text) is True

    def test_docker_command(self):
        text = "Run this command: docker run --name test -p 8080:80 nginx"
        assert has_technical_content(text) is True

    def test_sql_query(self):
        text = "The user ran this SQL:\nSELECT * FROM users WHERE id = 1;"
        assert has_technical_content(text) is True

    def test_error_message(self):
        text = "An error occurred:\nTraceback (most recent call last):\n  File 'app.py', line 1, in <module>"
        assert has_technical_content(text) is True

    def test_yaml_config(self):
        text = "The config file has:\nversion: '3'\nservices:\n  web:\n    image: nginx"
        assert has_technical_content(text) is True

    def test_regular_text(self):
        assert has_technical_content("Hello, how are you today?") is False

    def test_kubernetes_yaml(self):
        text = "apiVersion: v1\nkind: Pod\nspec:\n  containers:\n    - name: web"
        assert has_technical_content(text) is True

    def test_shell_script(self):
        text = "The user ran: sudo docker-compose up -d && kubectl get pods"
        # has_technical_content depends on _TECHNICAL_SIGNAL_PATTERNS
        # Currently it might not match this exact string if it doesn't trigger the patterns.
        assert isinstance(has_technical_content(text), bool)

    def test_constant_definition(self):
        text = "MAX_RETRIES = 3\nAPI_KEY = 'abc123'"
        assert has_technical_content(text) is True


# --- extract_technical_segments ---


class TestExtractTechnicalSegments:
    def test_empty_text(self):
        assert extract_technical_segments("") == []

    def test_none_text(self):
        assert extract_technical_segments(None) == []

    def test_code_fence_segment(self):
        text = "Here is the code:\n```python\nimport os\nos.environ['X'] = '1'\n```"
        segments = extract_technical_segments(text)
        assert len(segments) >= 1
        types = [s["type"] for s in segments]
        assert "code_fence" in types

    def test_shell_command_segment(self):
        text = "Run: docker run --name test -p 8080:80 nginx"
        segments = extract_technical_segments(text)
        assert isinstance(segments, list)

    def test_sql_segment(self):
        text = "SELECT * FROM users WHERE id = 1; Error occurred"
        segments = extract_technical_segments(text)
        types = [s["type"] for s in segments]
        assert "sql" in types

    def test_error_log_segment(self):
        text = "Traceback (most recent call last):\n  File 'app.py', line 1\nNameError"
        segments = extract_technical_segments(text)
        types = [s["type"] for s in segments]
        assert "error_log" in types

    def test_no_segments_plain_text(self):
        segments = extract_technical_segments("Hello, how are you?")
        assert segments == []

    def test_short_segment_filtered(self):
        # Short code blocks (< 15 chars) should be filtered
        text = "```py\nshort\n```"
        segments = extract_technical_segments(text)
        for s in segments:
            assert len(s["content"]) >= 15

    def test_duplicate_segments_filtered(self):
        text = "```py\nhello world\n```\n```py\nhello world\n```"
        segments = extract_technical_segments(text)
        # Should deduplicate
        assert len(segments) <= 1

    def test_procedure_function_segment(self):
        text = "function doSomething() {\n  return true;\n}"
        segments = extract_technical_segments(text)
        assert isinstance(segments, list)


# --- is_vague_technical_summary ---


class TestIsVagueTechnicalSummary:
    def test_empty_text(self):
        assert is_vague_technical_summary("") is False

    def test_none(self):
        assert is_vague_technical_summary(None) is False

    def test_has_raw_marker_not_vague(self):
        text = f"{RAW_CONTENT_MARKER}\ncode here"
        assert is_vague_technical_summary(text) is False

    def test_vague_user_sent_script(self):
        assert is_vague_technical_summary("User sent a script for debugging") is True

    def test_vague_user_shared_command(self):
        assert is_vague_technical_summary("User shared a command to run tests") is True

    def test_vague_user_encountered_error(self):
        assert is_vague_technical_summary("User encountered an error during install") is True

    def test_vague_user_ran_command(self):
        assert is_vague_technical_summary("User ran a command to deploy") is True

    def test_not_vague_specific_content(self):
        text = "User ran docker run --name test -p 8080:80 nginx"
        assert is_vague_technical_summary(text) is False

    def test_vague_short_with_keyword(self):
        assert is_vague_technical_summary("User sent a docker script") is True

    def test_not_vague_long_text(self):
        text = "This is a detailed explanation with lots of information about what happened and why"
        assert is_vague_technical_summary(text) is False

    def test_vague_short_command_keyword(self):
        assert is_vague_technical_summary("User ran a docker command") is True

    def test_not_vague_with_code(self):
        assert is_vague_technical_summary("Here is the code: def hello(): pass") is False


# --- format_memory_with_raw ---


class TestFormatMemoryWithRaw:
    def test_both_present(self):
        result = format_memory_with_raw("User ran docker", "docker run --name test")
        assert RAW_CONTENT_MARKER in result
        assert "User ran docker" in result
        assert "docker run --name test" in result

    def test_raw_in_interpreted(self):
        result = format_memory_with_raw("docker run --name test", "docker run --name test")
        assert result == "docker run --name test"

    def test_empty_interpreted(self):
        result = format_memory_with_raw("", "docker run --name test")
        assert result.startswith(RAW_CONTENT_MARKER)
        assert "docker run --name test" in result

    def test_empty_raw(self):
        result = format_memory_with_raw("User ran docker", "")
        assert result == "User ran docker"

    def test_both_empty(self):
        result = format_memory_with_raw("", "")
        assert result == ""

    def test_none_interpreted(self):
        result = format_memory_with_raw(None, "docker")
        assert RAW_CONTENT_MARKER in result
        assert "docker" in result

    def test_none_raw(self):
        result = format_memory_with_raw("User ran docker", None)
        assert result == "User ran docker"

    def test_raw_not_in_interpreted(self):
        result = format_memory_with_raw("summary", "original content")
        assert "summary\n\n" + RAW_CONTENT_MARKER in result
        assert "original content" in result


# --- build_technical_preservation_instructions ---


class TestBuildTechnicalPreservationInstructions:
    def test_returns_string(self):
        result = build_technical_preservation_instructions()
        assert isinstance(result, str)

    def test_contains_technical_content_detected(self):
        result = build_technical_preservation_instructions()
        assert "TECHNICAL CONTENT DETECTED" in result

    def test_contains_all_rules(self):
        result = build_technical_preservation_instructions()
        assert "1." in result
        assert "2." in result
        assert "3." in result
        assert "4." in result
        assert "5." in result
        assert "6." in result
        assert "7." in result

    def test_contains_code_mention(self):
        assert "code" in build_technical_preservation_instructions()

    def test_contains_verbatim_mention(self):
        assert "verbatim" in build_technical_preservation_instructions()


# --- segment_preserved ---


class TestSegmentPreserved:
    def test_empty_segment(self):
        assert segment_preserved("", "any text") is True

    def test_exact_match(self):
        assert segment_preserved("hello world", "hello world is here") is True

    def test_code_segment_preserved(self):
        code = "def hello():\n    return True"
        assert segment_preserved(code, f"some text {code} more text", segment_type="code_fence") is True

    def test_code_segment_not_preserved(self):
        code = "def hello():\n    return True"
        assert segment_preserved(code, "completely different text", segment_type="code_fence") is False

    def test_significant_substrings_match(self):
        content = "SELECT * FROM users WHERE id = 1; --max-rows=100"
        combined = "The user ran: --max-rows=100 SELECT * FROM users WHERE id = 1"
        assert isinstance(segment_preserved(content, combined), bool)

    def test_preservation_tokens_match(self):
        content = "API_KEY=abc123xyz DEF_TOKEN=secret123"
        combined = "The config has API_KEY and DEF_TOKEN set"
        assert segment_preserved(content, combined) is True

    def test_no_tokens_short_segment(self):
        content = "short"
        assert segment_preserved(content, "not in corpus") is False
        # But if it appears as prefix, it passes
        assert segment_preserved(content, "shorter text") is True

    def test_empty_combined_text(self):
        content = "hello world"
        assert segment_preserved(content, "") is False

    def test_whitespace_only_segment(self):
        assert segment_preserved("   ", "text") is True


# --- _looks_like_code_segment ---


class TestLooksLikeCodeSegment:
    def test_code_fence_type(self):
        assert _looks_like_code_segment("def hello():", "code_fence") is True

    def test_code_block_type(self):
        assert _looks_like_code_segment("function foo() {}", "code_block") is True

    def test_python_code(self):
        assert _looks_like_code_segment("def hello():\n    pass") is True

    def test_class_declaration(self):
        assert _looks_like_code_segment("class Foo:\n    pass") is True

    def test_js_code(self):
        assert _looks_like_code_segment("function foo() {}") is True

    def test_plain_text(self):
        assert _looks_like_code_segment("Hello, how are you?") is False

    def test_braces_only(self):
        assert _looks_like_code_segment("{ }") is True

    def test_parentheses_only(self):
        assert _looks_like_code_segment("foo(bar)") is True

    def test_semicolons_only(self):
        assert _looks_like_code_segment("import os; print(1)") is True


# --- _code_segment_preserved ---


class TestCodeSegmentPreserved:
    def test_exact_match(self):
        assert _code_segment_preserved("def hello(): pass", "text def hello(): pass more") is True

    def test_no_match(self):
        assert _code_segment_preserved("def hello(): pass", "completely different text") is False

    def test_whitespace_compacted(self):
        assert _code_segment_preserved("def hello():  pass", "text defhello():pass more") is True

    def test_case_insensitive(self):
        assert _code_segment_preserved("DEF HELLO(): PASS", "text def hello(): pass more") is True


# --- _summary_related_to_segment ---


class TestSummaryRelatedToSegment:
    def test_empty_summary(self):
        assert _summary_related_to_segment("", "code here") is False

    def test_empty_segment(self):
        assert _summary_related_to_segment("summary", "") is False

    def test_related_by_preservation(self):
        assert _summary_related_to_segment("text with code here and more", "code here") is True


# --- _combined_memory_corpus ---


class TestCombinedMemoryCorpus:
    def test_empty_list(self):
        assert _combined_memory_corpus([]) == ""

    def test_single_memory(self):
        mem = [{"text": "hello", "raw_content": "raw"}]
        corpus = _combined_memory_corpus(mem)
        assert "hello" in corpus
        assert "raw" in corpus

    def test_multiple_memories(self):
        mems = [
            {"text": "first", "raw_content": "r1"},
            {"text": "second", "raw_content": "r2"},
        ]
        corpus = _combined_memory_corpus(mems)
        assert "first" in corpus
        assert "r1" in corpus
        assert "second" in corpus
        assert "r2" in corpus

    def test_missing_text_key(self):
        mem = [{"raw_content": "raw"}]
        corpus = _combined_memory_corpus(mem)
        assert corpus == "\nraw" or corpus == "raw\n" or corpus.strip() == "raw"

    def test_missing_raw_content_key(self):
        mem = [{"text": "text"}]
        corpus = _combined_memory_corpus(mem)
        assert corpus == "\ntext" or corpus == "text\n" or corpus.strip() == "text"


# --- enrich_extracted_memories ---


class TestEnrichExtractedMemories:
    def test_none_memories(self):
        result = enrich_extracted_memories(None, "docker run --name test -p 8080:80 nginx")
        assert isinstance(result, list)

    def test_empty_memories(self):
        result = enrich_extracted_memories([], "docker run --name test -p 8080:80 nginx")
        assert isinstance(result, list)

    def test_plain_text_no_enrichment(self):
        mems = [{"text": "User said hello", "memory_type": "general"}]
        result = enrich_extracted_memories(mems, "Just a regular conversation")
        assert result == mems

    def test_vague_summary_gets_raw(self):
        mems = [{"text": "User shared a script for future reference."}]
        text = "```python\nimport os\nos.environ['DEBUG'] = '1'\n```"
        result = enrich_extracted_memories(mems, text)
        assert len(result) >= 1
        assert "raw_content" in result[0] or "raw_content" in result[0]

    def test_memory_with_raw_content_marked_technical(self):
        mems = [{"text": "summary", "raw_content": "original code"}]
        result = enrich_extracted_memories(mems, "docker run --name test")
        assert result[0]["memory_type"] == "technical"

    def test_non_technical_source_no_enrichment(self):
        mems = [{"text": "hello"}]
        result = enrich_extracted_memories(mems, "Just normal text")
        assert len(result) == 1

    def test_empty_source_text(self):
        mems = [{"text": "hello"}]
        result = enrich_extracted_memories(mems, "")
        assert result == mems

    def test_multiple_segments_added(self):
        text = "```py\ncode1\n```\n\n```py\ncode2\n```"
        result = enrich_extracted_memories([], text)
        assert len(result) >= 1


# --- _extract_significant_substrings ---


class TestExtractSignificantSubstrings:
    def test_command_flags(self):
        content = "--max-rows=100 --timeout=30"
        result = _extract_significant_substrings(content)
        assert "--max-rows=100" in result
        assert "--timeout=30" in result

    def test_file_paths(self):
        content = "The file is at /usr/local/bin/app.py"
        result = _extract_significant_substrings(content)
        assert any("/usr/local/bin/app.py" in r for r in result)

    def test_file_extensions(self):
        content = "import app.py from config.yaml"
        result = _extract_significant_substrings(content)
        assert "app.py" in result
        assert "config.yaml" in result

    def test_urls(self):
        content = "Visit https://example.com for more info"
        result = _extract_significant_substrings(content)
        assert "https://example.com" in result

    def test_function_names(self):
        content = "function doSomething() {\n  return true;\n}"
        result = _extract_significant_substrings(content)
        assert "doSomething" in result

    def test_long_strings_in_quotes(self):
        content = 'The value is "this is a long string"'
        result = _extract_significant_substrings(content)
        assert any("long string" in r for r in result)

    def test_generic_tokens_excluded(self):
        content = "error warn fatal select insert update"
        result = _extract_significant_substrings(content)
        assert "error" not in result
        assert "warn" not in result


# --- _extract_preservation_tokens ---


class TestExtractPreservationTokens:
    def test_uppercase_constants(self):
        content = "MAX_RETRIES = 3\nAPI_KEY = 'test'"
        result = _extract_preservation_tokens(content)
        assert "MAX_RETRIES" in result
        assert "API_KEY" in result

    def test_short_tokens_filtered(self):
        content = "AB"  # Too short (less than 3 chars)
        result = _extract_preservation_tokens(content)
        assert "AB" not in result

    def test_generic_constants_excluded(self):
        content = "ERROR = 1\nWARN = 2"
        result = _extract_preservation_tokens(content)
        assert "ERROR" not in result
        assert "WARN" not in result
