"""Tests for ``mem0.llms.openai.OpenAILLM``."""

import json
import os
from unittest import TestCase, mock

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


# -- helpers --

def _make_mock_response(content="Hello world", has_tools=False, reasoning_content=None):
    choice_mock = mock.MagicMock()
    msg = mock.MagicMock()
    msg.content = content
    msg.reasoning_content = reasoning_content
    msg.tool_calls = []
    choice_mock.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice_mock]
    return resp


def _make_mock_response_with_tools():
    tc1 = mock.MagicMock()
    tc1.function.name = "search"
    tc1.function.arguments = '{"query": "hello world"}'
    msg = mock.MagicMock()
    msg.content = "Let me search."
    msg.tool_calls = [tc1]
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


def _make_mock_response_empty():
    msg = mock.MagicMock()
    msg.content = ""
    msg.reasoning_content = None
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestOpenAILLM(TestCase):
    """Tests for OpenAILLM initialization and response handling."""

    def setUp(self):
        self.cfg = OpenAIConfig(model="gpt-4o", api_key="sk-test")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_initialization(self, mock_openai_cls):
        OpenAILLM(self.cfg)
        mock_openai_cls.assert_called_once_with(
            api_key="sk-test",
            base_url="https://api.openai.com/v1",
        )

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_custom_base_url(self, mock_openai_cls):
        cfg = OpenAIConfig(
            model="gpt-4o",
            api_key="sk-test",
            openai_base_url="https://custom.openai.com/v1",
        )
        OpenAILLM(cfg)
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://custom.openai.com/v1")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_default_model(self, mock_openai_cls):
        cfg = OpenAIConfig(api_key="sk-test")
        llm = OpenAILLM(cfg)
        # OpenAILLM defaults to "gpt-5-mini" when model is not provided
        self.assertEqual(llm.config.model, "gpt-5-mini")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_text_completion(self, mock_openai_cls):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hi there!")
        mock_openai_cls.return_value = mock_client

        llm = OpenAILLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hello"}])
        self.assertEqual(result, "Hi there!")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_structured_response_with_tools(self, mock_openai_cls):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response_with_tools()
        mock_openai_cls.return_value = mock_client

        llm = OpenAILLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        result = llm.generate_response([{"role": "user", "content": "search"}], tools=tools)
        self.assertIn("tool_calls", result)
        self.assertEqual(len(result["tool_calls"]), 1)
        self.assertEqual(result["tool_calls"][0]["name"], "search")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_empty_response_returns_empty_string(self, mock_openai_cls):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response_empty()
        mock_openai_cls.return_value = mock_client

        llm = OpenAILLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hello"}])
        self.assertEqual(result, "")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_response_callback_invoked(self, mock_openai_cls):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        callback = mock.MagicMock()
        cfg = OpenAIConfig(
            model="gpt-4o",
            api_key="sk-test",
            response_callback=callback,
        )
        llm = OpenAILLM(cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        callback.assert_called_once()

    @mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-key"})
    @mock.patch("mem0.llms.openai.OpenAI")
    def test_openrouter_initialization(self, mock_openai_cls):
        cfg = OpenAIConfig(model="anthropic/claude-3", api_key="sk-test")
        OpenAILLM(cfg)
        mock_openai_cls.assert_called_once()
        call_kwargs = mock_openai_cls.call_args.kwargs
        self.assertEqual(call_kwargs["api_key"], "or-key")

    @mock.patch("mem0.llms.openai.OpenAI")
    def test_store_param_not_sent_by_default(self, mock_openai_cls):
        """store defaults to None, meaning it should NOT be sent to the API."""
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai_cls.return_value = mock_client

        llm = OpenAILLM(self.cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("store", call_kwargs)
