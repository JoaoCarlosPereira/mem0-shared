"""Tests for technical content detection and preservation during memory extraction."""

import os
import sys

import pytest

# Ensure repo-root mem0 package is importable when running from openmemory/api.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from mem0.configs.prompts import ADDITIVE_EXTRACTION_PROMPT, generate_additive_extraction_prompt
from mem0.memory.technical_content import (
    RAW_CONTENT_MARKER,
    build_technical_preservation_instructions,
    enrich_extracted_memories,
    extract_technical_segments,
    format_memory_with_raw,
    has_technical_content,
    is_vague_technical_summary,
    segment_preserved,
)


SHELL_COMMAND = (
    "./llama-cli --model /models/Qwen3-35B.gguf --n-gpu-layers 35 "
    "--ctx-size 8192 --batch-size 512 --threads 8 --port 8080"
)

PYTHON_BLOCK = """```python
def worker_timeout_fix(concurrency: int = 4):
    return asyncio.Semaphore(concurrency)
```"""

SQL_ERROR = (
    "SELECT u.id, u.email FROM users u JOIN orders o ON o.user_id = u.id "
    "WHERE o.status = 'pending';\n"
    "ERROR: relation \"orders\" does not exist at character 42"
)

DELPHI_SNIPPET = """procedure TForm1.btnSalvarClick(Sender: TObject);
begin
  Query1.SQL.Text := 'SELECT * FROM CLIENTES WHERE ID = :ID';
  Query1.ParamByName('ID').AsInteger := edtID.Text;
  Query1.Open;
end;"""

YAML_CONFIG = """version: '3.8'
services:
  openmemory-mcp:
    image: openmemory/api:latest
    environment:
      MEM0_ALLOW_MEMORY_DELETE: '0'
    ports:
      - '8765:8765'
"""

LOG_WITH_ERROR = (
    "2025-07-02T14:22:01Z ERROR write_worker job_id=abc failed: "
    "Connection refused to http://localhost:11434/v1/chat/completions"
)


class TestTechnicalContentDetection:
    def test_detects_code_fence(self):
        assert has_technical_content(PYTHON_BLOCK)

    def test_detects_shell_command(self):
        assert has_technical_content(f"Run this:\n{SHELL_COMMAND}")

    def test_detects_sql_and_error(self):
        assert has_technical_content(SQL_ERROR)

    def test_detects_delphi(self):
        assert has_technical_content(DELPHI_SNIPPET)

    def test_detects_yaml(self):
        assert has_technical_content(YAML_CONFIG)

    def test_detects_error_log(self):
        assert has_technical_content(LOG_WITH_ERROR)

    def test_ignores_plain_conversation(self):
        assert not has_technical_content("User likes hiking on weekends with friends.")


class TestTechnicalSegmentExtraction:
    def test_extracts_fenced_code(self):
        segments = extract_technical_segments(PYTHON_BLOCK)
        assert any("asyncio.Semaphore" in seg["content"] for seg in segments)

    def test_extracts_shell_flags(self):
        segments = extract_technical_segments(SHELL_COMMAND)
        joined = "\n".join(seg["content"] for seg in segments)
        assert "--n-gpu-layers 35" in joined
        assert "/models/Qwen3-35B.gguf" in joined

    def test_extracts_sql_statement(self):
        segments = extract_technical_segments(SQL_ERROR)
        joined = "\n".join(seg["content"] for seg in segments)
        assert "SELECT u.id, u.email" in joined
        assert 'relation "orders" does not exist' in joined


class TestVagueSummaryDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "User sent a script for deployment.",
            "User works with code in this project.",
            "User configured a service.",
            "User had an error while testing.",
        ],
    )
    def test_flags_generic_technical_memories(self, text):
        assert is_vague_technical_summary(text)

    def test_accepts_specific_memory(self):
        text = "User runs llama-cli with --n-gpu-layers 35 on /models/Qwen3-35B.gguf"
        assert not is_vague_technical_summary(text)


class TestEnrichExtractedMemories:
    def test_preserves_raw_content_from_llm_output(self):
        source = f"Command:\n{SHELL_COMMAND}"
        extracted = [
            {
                "id": "0",
                "text": "User runs llama.cpp with GPU layers on port 8080",
                "raw_content": SHELL_COMMAND,
                "attributed_to": "user",
            }
        ]
        result = enrich_extracted_memories(extracted, source)
        assert RAW_CONTENT_MARKER in result[0]["text"]
        assert "--n-gpu-layers 35" in result[0]["text"]
        assert result[0]["raw_content"] == SHELL_COMMAND

    def test_adds_artifact_when_llm_output_is_vague(self):
        source = f"Remember this:\n{SHELL_COMMAND}"
        extracted = [{"id": "0", "text": "User sent a command to run llama.cpp", "attributed_to": "user"}]
        result = enrich_extracted_memories(extracted, source)
        combined = "\n".join(m["text"] for m in result)
        assert "--ctx-size 8192" in combined
        assert "--batch-size 512" in combined
        assert not is_vague_technical_summary(combined)

    def test_creates_raw_memory_when_extraction_empty(self):
        source = f"```json\n{{\"service\": \"openmemory-mcp\", \"port\": 8765}}\n```"
        result = enrich_extracted_memories([], source)
        assert len(result) >= 1
        combined = "\n".join(m.get("text", "") + m.get("raw_content", "") for m in result)
        assert "openmemory-mcp" in combined
        assert "8765" in combined

    def test_mixed_explanation_and_code(self):
        source = f"Fix worker timeout:\n{PYTHON_BLOCK}"
        extracted = [
            {
                "id": "0",
                "text": "User increased asyncio semaphore concurrency to fix worker timeout",
                "attributed_to": "user",
            }
        ]
        result = enrich_extracted_memories(extracted, source)
        combined = "\n".join(m["text"] for m in result)
        assert "asyncio.Semaphore" in combined
        assert "concurrency: int = 4" in combined

    def test_sql_flags_and_table_names_preserved(self):
        source = SQL_ERROR
        extracted = [{"id": "0", "text": "User had a database error on a join query", "attributed_to": "user"}]
        result = enrich_extracted_memories(extracted, source)
        combined = "\n".join(m.get("text", "") + m.get("raw_content", "") for m in result)
        assert "orders" in combined
        assert "users" in combined
        assert "character 42" in combined

    def test_delphi_procedure_preserved(self):
        source = DELPHI_SNIPPET
        extracted = [{"id": "0", "text": "User shared Delphi code", "attributed_to": "user"}]
        result = enrich_extracted_memories(extracted, source)
        combined = "\n".join(m.get("text", "") + m.get("raw_content", "") for m in result)
        assert "TForm1.btnSalvarClick" in combined
        assert "CLIENTES" in combined

    def test_yaml_service_and_env_preserved(self):
        source = YAML_CONFIG
        extracted = [{"id": "0", "text": "User shared docker compose config", "attributed_to": "user"}]
        result = enrich_extracted_memories(extracted, source)
        combined = "\n".join(m.get("text", "") + m.get("raw_content", "") for m in result)
        assert "openmemory-mcp" in combined
        assert "MEM0_ALLOW_MEMORY_DELETE" in combined

    def test_error_log_preserved(self):
        source = LOG_WITH_ERROR
        extracted = [{"id": "0", "text": "User encountered a write worker error", "attributed_to": "user"}]
        result = enrich_extracted_memories(extracted, source)
        combined = "\n".join(m.get("text", "") + m.get("raw_content", "") for m in result)
        assert "Connection refused" in combined
        assert "localhost:11434" in combined


class TestPromptIntegration:
    def test_additive_prompt_documents_raw_content_field(self):
        assert "raw_content" in ADDITIVE_EXTRACTION_PROMPT
        assert "Technical Content Preservation" in ADDITIVE_EXTRACTION_PROMPT
        assert "When in doubt, preserve" in ADDITIVE_EXTRACTION_PROMPT

    def test_prompt_builder_injects_technical_section(self):
        prompt = generate_additive_extraction_prompt(
            new_messages=f"user: {SHELL_COMMAND}\n",
            technical_preservation_instructions=build_technical_preservation_instructions(),
        )
        assert "## Technical Content Preservation" in prompt
        assert "verbatim" in prompt.lower()


class TestFormatAndSegmentHelpers:
    def test_format_memory_with_raw(self):
        formatted = format_memory_with_raw("User runs llama.cpp", SHELL_COMMAND)
        assert "User runs llama.cpp" in formatted
        assert RAW_CONTENT_MARKER in formatted
        assert "--port 8080" in formatted

    def test_segment_preserved_requires_distinctive_tokens(self):
        assert segment_preserved(SHELL_COMMAND, SHELL_COMMAND)
        assert not segment_preserved(SHELL_COMMAND, "User runs llama.cpp for inference")
