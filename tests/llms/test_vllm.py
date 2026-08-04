"""Tests for ``mem0.llms.vllm.VllmLLM``."""

from unittest import TestCase, mock

from mem0.configs.llms.vllm import VllmConfig
from mem0.llms.vllm import VllmLLM


def _make_mock_response(content="vLLM response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestVllmLLM(TestCase):
    """Tests for VllmLLM initialization and response handling."""

    def setUp(self):
        self.cfg = VllmConfig(model="Qwen/Qwen2.5-32B-Instruct", api_key="vllm-key")

    @mock.patch("mem0.llms.vllm.OpenAI")
    def test_initialization(self, mock_openai):
        VllmLLM(self.cfg)
        mock_openai.assert_called_once()

    @mock.patch("mem0.llms.vllm.OpenAI")
    def test_default_model(self, mock_openai):
        cfg = VllmConfig(api_key="vllm-key")
        llm = VllmLLM(cfg)
        self.assertEqual(llm.config.model, "Qwen/Qwen2.5-32B-Instruct")

    @mock.patch("mem0.llms.vllm.OpenAI")
    def test_custom_base_url(self, mock_openai):
        cfg = VllmConfig(
            model="test-model",
            api_key="vllm-key",
            vllm_base_url="http://localhost:9000/v1",
        )
        VllmLLM(cfg)
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "http://localhost:9000/v1")

    @mock.patch("mem0.llms.vllm.OpenAI")
    def test_text_completion(self, mock_openai):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_openai.return_value = mock_client

        llm = VllmLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.vllm.OpenAI")
    def test_default_api_key_fallback(self, mock_openai):
        """When no API key is given, vllm uses default 'vllm-api-key'."""
        cfg = VllmConfig(model="test-model")
        VllmLLM(cfg)
        call_kwargs = mock_openai.call_args.kwargs
        # When no env var and no config key, defaults to "vllm-api-key"
        self.assertEqual(call_kwargs["api_key"], "vllm-api-key")

    @mock.patch("mem0.llms.vllm.OpenAI")
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

        llm = VllmLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")
