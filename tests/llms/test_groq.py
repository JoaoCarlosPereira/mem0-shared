"""Tests for ``mem0.llms.groq.GroqLLM``."""

import sys
from unittest import TestCase, mock

# Mock optional dependencies before importing the module.
sys.modules["groq"] = mock.MagicMock()

from mem0.llms.groq import GroqLLM


def _make_mock_response(content="Groq response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestGroqLLM(TestCase):
    """Tests for GroqLLM initialization and response handling."""

    def setUp(self):
        self.cfg = mock.MagicMock()
        self.cfg.model = "llama-3.3-70b-versatile"
        self.cfg.temperature = 0.1
        self.cfg.max_tokens = 2000
        self.cfg.top_p = 0.1
        self.cfg.api_key = "gqo-test-key"

    @mock.patch("mem0.llms.groq.Groq")
    def test_initialization(self, mock_groq):
        GroqLLM(self.cfg)
        mock_groq.assert_called_once_with(api_key="gqo-test-key")

    @mock.patch("mem0.llms.groq.Groq")
    def test_default_model(self, mock_groq):
        cfg = mock.MagicMock()
        cfg.model = None
        cfg.temperature = 0.1
        cfg.max_tokens = 2000
        cfg.top_p = 0.1
        cfg.api_key = "gqo-test-key"
        GroqLLM(cfg)
        self.assertEqual(cfg.model, "llama-3.3-70b-versatile")

    @mock.patch("mem0.llms.groq.Groq")
    def test_text_completion(self, mock_groq):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_groq.return_value = mock_client

        llm = GroqLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.groq.Groq")
    def test_tools_passed(self, mock_groq):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_groq.return_value = mock_client

        llm = GroqLLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        llm.generate_response([{"role": "user", "content": "hi"}], tools=tools)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertIn("tools", call_kwargs)

    @mock.patch("mem0.llms.groq.Groq")
    def test_empty_response(self, mock_groq):
        msg = mock.MagicMock()
        msg.content = ""
        msg.tool_calls = []
        choice = mock.MagicMock()
        choice.message = msg
        resp = mock.MagicMock()
        resp.choices = [choice]

        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = resp
        mock_groq.return_value = mock_client

        llm = GroqLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")
