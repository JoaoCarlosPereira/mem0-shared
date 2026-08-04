"""Tests for ``mem0.llms.together.TogetherLLM``."""

import sys
from unittest import TestCase, mock

# Mock optional dependencies before importing the module.
sys.modules["together"] = mock.MagicMock()

from mem0.llms.together import TogetherLLM


def _make_mock_response(content="Together response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestTogetherLLM(TestCase):
    """Tests for TogetherLLM initialization and response handling."""

    def setUp(self):
        self.cfg = mock.MagicMock()
        self.cfg.model = "mistralai/Mixtral-8x7B-Instruct-v0.1"
        self.cfg.temperature = 0.1
        self.cfg.max_tokens = 2000
        self.cfg.top_p = 0.1
        self.cfg.api_key = "tog-test-key"

    @mock.patch("mem0.llms.together.Together")
    def test_initialization(self, mock_together):
        TogetherLLM(self.cfg)
        mock_together.assert_called_once_with(api_key="tog-test-key")

    @mock.patch("mem0.llms.together.Together")
    def test_default_model(self, mock_together):
        cfg = mock.MagicMock()
        cfg.model = None
        cfg.temperature = 0.1
        cfg.max_tokens = 2000
        cfg.top_p = 0.1
        cfg.api_key = "tog-test-key"
        TogetherLLM(cfg)
        self.assertEqual(cfg.model, "mistralai/Mixtral-8x7B-Instruct-v0.1")

    @mock.patch("mem0.llms.together.Together")
    def test_text_completion(self, mock_together):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_together.return_value = mock_client

        llm = TogetherLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.together.Together")
    def test_kwargs_merged(self, mock_together):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_together.return_value = mock_client

        llm = TogetherLLM(self.cfg)
        llm.generate_response([{"role": "user", "content": "hi"}], extra_param=42)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["extra_param"], 42)

    @mock.patch("mem0.llms.together.Together")
    def test_empty_response(self, mock_together):
        msg = mock.MagicMock()
        msg.content = ""
        msg.tool_calls = []
        choice = mock.MagicMock()
        choice.message = msg
        resp = mock.MagicMock()
        resp.choices = [choice]

        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = resp
        mock_together.return_value = mock_client

        llm = TogetherLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")
