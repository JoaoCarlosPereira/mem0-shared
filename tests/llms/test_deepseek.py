"""Tests for ``mem0.llms.deepseek.DeepSeekLLM``."""

from unittest import TestCase, mock

from mem0.configs.llms.deepseek import DeepSeekConfig
from mem0.llms.deepseek import DeepSeekLLM


def _make_mock_response(content="DeepSeek response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestDeepSeekLLM(TestCase):
    """Tests for DeepSeekLLM initialization and response handling."""

    def setUp(self):
        self.cfg = DeepSeekConfig(model="deepseek-chat", api_key="sk-ds-test")

    @mock.patch("mem0.llms.deepseek.OpenAI")
    def test_initialization(self, mock_openai):
        DeepSeekLLM(self.cfg)
        mock_openai.assert_called_once()

    @mock.patch("mem0.llms.deepseek.OpenAI")
    def test_default_model(self, mock_openai):
        cfg = DeepSeekConfig(api_key="sk-ds-test")
        llm = DeepSeekLLM(cfg)
        self.assertEqual(llm.config.model, "deepseek-chat")

    @mock.patch("mem0.llms.deepseek.OpenAI")
    def test_custom_base_url(self, mock_openai):
        cfg = DeepSeekConfig(api_key="sk-ds-test", deepseek_base_url="https://custom.deepseek.com")
        DeepSeekLLM(cfg)
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://custom.deepseek.com")

    @mock.patch("mem0.llms.deepseek.OpenAI")
    def test_text_completion(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_openai.return_value = mock_client

        llm = DeepSeekLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.deepseek.OpenAI")
    def test_response_format_passed(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_openai.return_value = mock_client

        llm = DeepSeekLLM(self.cfg)
        llm.generate_response(
            [{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    @mock.patch("mem0.llms.deepseek.OpenAI")
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

        llm = DeepSeekLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")
