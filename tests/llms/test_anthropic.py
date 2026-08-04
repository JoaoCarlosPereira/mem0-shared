"""Tests for ``mem0.llms.anthropic.AnthropicLLM``."""

from unittest import TestCase, mock

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.llms.anthropic import AnthropicLLM


def _make_mock_response(text="Hello", tool_blocks=False):
    class TextBlock:
        def __init__(self):
            self.type = "text"
            self.text = text

    class ToolUseBlock:
        def __init__(self):
            self.type = "tool_use"
            self.name = "calculate"
            self.input = {"expr": "1+1"}

    blocks = [TextBlock()]
    if tool_blocks:
        blocks.append(ToolUseBlock())

    resp = mock.MagicMock()
    resp.content = blocks
    return resp


def _make_mock_response_no_content():
    resp = mock.MagicMock()
    resp.content = []
    return resp


class TestAnthropicLLM(TestCase):
    """Tests for AnthropicLLM initialization and response handling."""

    def setUp(self):
        self.cfg = AnthropicConfig(model="claude-3-opus", api_key="sk-ant-test")

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_initialization(self, mock_anthropic):
        AnthropicLLM(self.cfg)
        mock_anthropic.Anthropic.assert_called_once_with(api_key="sk-ant-test")

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_default_model(self, mock_anthropic):
        cfg = AnthropicConfig(api_key="sk-ant-test")
        llm = AnthropicLLM(cfg)
        # AnthropicLLM defaults to "claude-sonnet-4-6" when model is not provided
        self.assertEqual(llm.config.model, "claude-sonnet-4-6")

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_text_completion(self, mock_anthropic):
        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(text="Hi!")
        mock_anthropic.Anthropic.return_value = mock_client

        llm = AnthropicLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hello"}])
        self.assertEqual(result, "Hi!")

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_system_message_extracted(self, mock_anthropic):
        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = _make_mock_response()
        mock_anthropic.Anthropic.return_value = mock_client

        llm = AnthropicLLM(self.cfg)
        llm.generate_response([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "hello"},
        ])
        call_kwargs = mock_client.messages.create.call_args.kwargs
        self.assertEqual(call_kwargs["system"], "You are a helpful assistant.")

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_tool_calls_parsed(self, mock_anthropic):
        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = _make_mock_response(
            tool_blocks=True, text="Let me calculate."
        )
        mock_anthropic.Anthropic.return_value = mock_client

        llm = AnthropicLLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "calculate", "parameters": {}}}]
        result = llm.generate_response([{"role": "user", "content": "calculate"}], tools=tools)
        self.assertIn("tool_calls", result)
        self.assertEqual(result["tool_calls"][0]["name"], "calculate")

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_empty_response(self, mock_anthropic):
        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = _make_mock_response_no_content()
        mock_anthropic.Anthropic.return_value = mock_client

        llm = AnthropicLLM(self.cfg)
        # The source code accesses content[0] without guard for empty list.
        # We verify that calling it raises IndexError (current behavior).
        with self.assertRaises(IndexError):
            llm.generate_response([{"role": "user", "content": "hello"}])

    @mock.patch("mem0.llms.anthropic.anthropic")
    def test_temperature_only_when_both_set(self, mock_anthropic):
        """Anthropic forbids both temperature and top_p. When both set, only temperature is sent."""
        mock_client = mock.MagicMock()
        mock_client.messages.create.return_value = _make_mock_response()
        mock_anthropic.Anthropic.return_value = mock_client

        # Create config with both temperature and top_p set
        cfg = AnthropicConfig(
            model="claude-3-opus",
            api_key="sk-ant-test",
            temperature=0.5,
            top_p=0.9,
        )
        llm = AnthropicLLM(cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.messages.create.call_args.kwargs
        self.assertIn("temperature", call_kwargs)
        self.assertNotIn("top_p", call_kwargs)
