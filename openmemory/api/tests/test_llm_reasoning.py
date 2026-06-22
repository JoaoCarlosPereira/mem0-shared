"""Tests for Qwen3 / llama.cpp reasoning response handling."""

from types import SimpleNamespace

from mem0.llms.openai import OpenAILLM
from mem0.memory.utils import remove_code_blocks


class TestOpenAIReasoningFallback:
    def _llm(self):
        return OpenAILLM(config={"model": "test-model", "api_key": "test"})

    def test_uses_content_when_present(self):
        llm = self._llm()
        message = SimpleNamespace(content='{"memory": []}', reasoning_content="thinking...")
        assert llm._message_text(message) == '{"memory": []}'

    def test_falls_back_to_reasoning_content_when_content_empty(self):
        llm = self._llm()
        message = SimpleNamespace(
            content="",
            reasoning_content='{"memory": [{"id": "0", "text": "fact", "attributed_to": "user"}]}',
        )
        assert '"memory"' in llm._message_text(message)

    def test_parse_response_without_tools_returns_reasoning_fallback(self):
        llm = self._llm()
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="",
                        reasoning_content='{"memory": [{"id": "0", "text": "x", "attributed_to": "user"}]}',
                    )
                )
            ]
        )
        parsed = llm._parse_response(response, tools=None)
        assert parsed.startswith('{"memory"')


class TestRemoveCodeBlocks:
    def test_strips_think_tags(self):
        raw = (
            "<think>internal reasoning</think>\n"
            '{"memory": [{"id": "0", "text": "User likes pizza", "attributed_to": "user"}]}'
        )
        cleaned = remove_code_blocks(raw)
        assert cleaned.startswith('{"memory"')
        assert "internal reasoning" not in cleaned

    def test_strips_redacted_thinking_tags(self):
        raw = (
            "<think>hidden</think>\n"
            '{"memory": []}'
        )
        cleaned = remove_code_blocks(raw)
        assert cleaned == '{"memory": []}'
