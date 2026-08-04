"""Tests for ``mem0.llms.litellm.LiteLLM``."""

import sys
from unittest import TestCase, mock

# Mock optional dependencies before importing the module.
_mock_litellm = mock.MagicMock()
sys.modules["litellm"] = _mock_litellm

from mem0.llms.litellm import LiteLLM


def _make_mock_response(content="LiteLLM response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestLiteLLM(TestCase):
    """Tests for LiteLLM initialization and response handling."""

    def setUp(self):
        self.cfg = mock.MagicMock()
        self.cfg.model = "gpt-5-mini"
        self.cfg.temperature = 0.1
        self.cfg.max_tokens = 2000
        self.cfg.top_p = 0.1

    @mock.patch("mem0.llms.litellm.litellm")
    def test_initialization(self, mock_litellm):
        LiteLLM(self.cfg)
        self.assertEqual(self.cfg.model, "gpt-5-mini")

    @mock.patch("mem0.llms.litellm.litellm")
    def test_default_model(self, mock_litellm):
        cfg = mock.MagicMock()
        cfg.model = None
        cfg.temperature = 0.1
        cfg.max_tokens = 2000
        cfg.top_p = 0.1
        LiteLLM(cfg)
        self.assertEqual(cfg.model, "gpt-5-mini")

    @mock.patch("mem0.llms.litellm.litellm")
    def test_text_completion(self, mock_litellm):
        mock_litellm.completion.return_value = _make_mock_response("Hello!")
        llm = LiteLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.litellm.litellm")
    def test_tools_passed(self, mock_litellm):
        mock_litellm.completion.return_value = _make_mock_response()
        mock_litellm.supports_function_calling.return_value = True

        llm = LiteLLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        llm.generate_response([{"role": "user", "content": "hi"}], tools=tools)
        call_kwargs = mock_litellm.completion.call_args.kwargs
        self.assertIn("tools", call_kwargs)

    @mock.patch("mem0.llms.litellm.litellm")
    def test_function_calling_not_supported_raises(self, mock_litellm):
        mock_litellm.supports_function_calling.return_value = False

        llm = LiteLLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        with self.assertRaises(ValueError) as ctx:
            llm.generate_response([{"role": "user", "content": "hi"}], tools=tools)
        self.assertIn("does not support function calling", str(ctx.exception))

    @mock.patch("mem0.llms.litellm.litellm")
    def test_response_format_passed(self, mock_litellm):
        mock_litellm.completion.return_value = _make_mock_response()
        llm = LiteLLM(self.cfg)
        llm.generate_response(
            [{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        call_kwargs = mock_litellm.completion.call_args.kwargs
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    @mock.patch("mem0.llms.litellm.litellm")
    def test_empty_response(self, mock_litellm):
        msg = mock.MagicMock()
        msg.content = ""
        msg.tool_calls = []
        choice = mock.MagicMock()
        choice.message = msg
        resp = mock.MagicMock()
        resp.choices = [choice]

        mock_litellm.completion.return_value = resp
        llm = LiteLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")

    @mock.patch("mem0.llms.litellm.litellm")
    def test_max_completion_tokens_for_gpt5(self, mock_litellm):
        cfg = mock.MagicMock()
        cfg.model = "gpt-5-mini"
        cfg.temperature = 0.1
        cfg.max_tokens = 2000
        cfg.top_p = 0.1
        mock_litellm.completion.return_value = _make_mock_response()

        llm = LiteLLM(cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_litellm.completion.call_args.kwargs
        self.assertIn("max_completion_tokens", call_kwargs)
        self.assertNotIn("max_tokens", call_kwargs)

    @mock.patch("mem0.llms.litellm.litellm")
    def test_max_tokens_for_non_gpt5(self, mock_litellm):
        cfg = mock.MagicMock()
        cfg.model = "gpt-4o"
        cfg.temperature = 0.1
        cfg.max_tokens = 2000
        cfg.top_p = 0.1
        mock_litellm.completion.return_value = _make_mock_response()

        llm = LiteLLM(cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_litellm.completion.call_args.kwargs
        self.assertIn("max_tokens", call_kwargs)
        self.assertNotIn("max_completion_tokens", call_kwargs)

    @mock.patch("mem0.llms.litellm.litellm")
    def test_tools_response_with_calls(self, mock_litellm):
        tc1 = mock.MagicMock()
        tc1.function.name = "calculate"
        tc1.function.arguments = '{"expr": "1+1"}'
        msg = mock.MagicMock()
        msg.content = "Let me calculate."
        msg.tool_calls = [tc1]
        choice = mock.MagicMock()
        choice.message = msg
        resp = mock.MagicMock()
        resp.choices = [choice]

        mock_litellm.completion.return_value = resp
        mock_litellm.supports_function_calling.return_value = True

        llm = LiteLLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "calculate", "parameters": {}}}]
        result = llm.generate_response([{"role": "user", "content": "calculate"}], tools=tools)
        self.assertIn("tool_calls", result)
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["name"], "calculate")
