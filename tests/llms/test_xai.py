"""Tests for ``mem0.llms.xai.XAILLM``."""

from unittest import TestCase, mock

from mem0.configs.llms.xai import XAIConfig
from mem0.llms.xai import XAILLM


def _make_mock_response(content="Grok response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestXAILLM(TestCase):
    """Tests for XAILLM initialization and response handling."""

    def setUp(self):
        self.cfg = XAIConfig(model="grok-2-latest", api_key="xai-key")

    @mock.patch("mem0.llms.xai.OpenAI")
    def test_initialization(self, mock_openai):
        XAILLM(self.cfg)
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["api_key"], "xai-key")

    @mock.patch("mem0.llms.xai.OpenAI")
    def test_default_model(self, mock_openai):
        cfg = XAIConfig(api_key="xai-key")
        llm = XAILLM(cfg)
        self.assertEqual(llm.config.model, "grok-2-latest")

    @mock.patch("mem0.llms.xai.OpenAI")
    def test_custom_base_url(self, mock_openai):
        cfg = XAIConfig(api_key="xai-key", xai_base_url="https://custom.xai.com/v1")
        XAILLM(cfg)
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://custom.xai.com/v1")

    @mock.patch("mem0.llms.xai.OpenAI")
    def test_text_completion(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_openai.return_value = mock_client

        llm = XAILLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.xai.OpenAI")
    def test_tools_passed(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai.return_value = mock_client

        llm = XAILLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        llm.generate_response([{"role": "user", "content": "hi"}], tools=tools)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertIn("tools", call_kwargs)

    @mock.patch("mem0.llms.xai.OpenAI")
    def test_empty_response(self, mock_openai):
        msg = mock.MagicMock()
        msg.content = ""
        msg.tool_calls = []
        choice = mock.MagicMock()
        choice.message = msg
        resp = mock.MagicMock()
        resp.choices = [choice]

        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = resp
        mock_openai.return_value = mock_client

        llm = XAILLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")
