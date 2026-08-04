"""Tests for ``mem0.llms.lmstudio.LMStudioLLM``."""

from unittest import TestCase, mock

from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.llms.lmstudio import LMStudioLLM


def _make_mock_response(content='{"answer": "hello"}'):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestLMStudioLLM(TestCase):
    """Tests for LMStudioLLM initialization and response handling."""

    def setUp(self):
        self.cfg = LMStudioConfig(model="meta-llama-3", api_key="lm-studio")

    @mock.patch("mem0.llms.lmstudio.OpenAI")
    def test_initialization(self, mock_openai):
        LMStudioLLM(self.cfg)
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["api_key"], "lm-studio")

    @mock.patch("mem0.llms.lmstudio.OpenAI")
    def test_default_model(self, mock_openai):
        cfg = LMStudioConfig(api_key="lm-studio")
        llm = LMStudioLLM(cfg)
        self.assertIn("llama", llm.config.model.lower())

    @mock.patch("mem0.llms.lmstudio.OpenAI")
    def test_default_api_key(self, mock_openai):
        cfg = LMStudioConfig(model="test-model")
        llm = LMStudioLLM(cfg)
        self.assertEqual(llm.config.api_key, "lm-studio")

    @mock.patch("mem0.llms.lmstudio.OpenAI")
    def test_text_completion(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response('{"result": "ok"}')
        mock_openai.return_value = mock_client

        llm = LMStudioLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertIn("result", result)

    @mock.patch("mem0.llms.lmstudio.OpenAI")
    def test_json_format_default(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai.return_value = mock_client

        llm = LMStudioLLM(self.cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    @mock.patch("mem0.llms.lmstudio.OpenAI")
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

        llm = LMStudioLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")
