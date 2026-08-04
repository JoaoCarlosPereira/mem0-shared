"""Tests for ``mem0.llms.ollama.OllamaLLM``."""

from unittest import TestCase, mock

from mem0.configs.llms.ollama import OllamaConfig
from mem0.llms.ollama import OllamaLLM


def _make_mock_response(content="Ollama response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = None
    resp = mock.MagicMock()
    resp.message = msg
    return resp


def _make_mock_response_dict(content="Ollama response"):
    return {"message": {"role": "assistant", "content": content, "tool_calls": None}}


class TestOllamaLLM(TestCase):
    """Tests for OllamaLLM initialization and response handling."""

    def setUp(self):
        self.cfg = OllamaConfig(model="llama3.1:70b")

    @mock.patch("mem0.llms.ollama.Client")
    def test_initialization(self, mock_client):
        OllamaLLM(self.cfg)
        mock_client.assert_called_once()

    @mock.patch("mem0.llms.ollama.Client")
    def test_default_model(self, mock_client):
        cfg = OllamaConfig()
        llm = OllamaLLM(cfg)
        self.assertEqual(llm.config.model, "llama3.1:70b")

    @mock.patch("mem0.llms.ollama.Client")
    def test_text_completion_object_response(self, mock_client):
        mock_inst = mock.MagicMock()
        mock_inst.chat.return_value = _make_mock_response("Hello!")
        mock_client.return_value = mock_inst

        llm = OllamaLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.ollama.Client")
    def test_text_completion_dict_response(self, mock_client):
        mock_inst = mock.MagicMock()
        mock_inst.chat.return_value = _make_mock_response_dict("Hello from dict!")
        mock_client.return_value = mock_inst

        llm = OllamaLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello from dict!")

    @mock.patch("mem0.llms.ollama.Client")
    def test_json_format_request(self, mock_client):
        mock_inst = mock.MagicMock()
        mock_inst.chat.return_value = _make_mock_response('{"ok": true}')
        mock_client.return_value = mock_inst

        llm = OllamaLLM(self.cfg)
        llm.generate_response(
            [{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        call_kwargs = mock_inst.chat.call_args.kwargs
        self.assertEqual(call_kwargs["format"], "json")

    @mock.patch("mem0.llms.ollama.Client")
    def test_options_included(self, mock_client):
        mock_inst = mock.MagicMock()
        mock_inst.chat.return_value = _make_mock_response()
        mock_client.return_value = mock_inst

        llm = OllamaLLM(self.cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_inst.chat.call_args.kwargs
        self.assertIn("options", call_kwargs)
        self.assertIn("temperature", call_kwargs["options"])

    @mock.patch("mem0.llms.ollama.Client")
    def test_empty_response(self, mock_client):
        mock_inst = mock.MagicMock()
        mock_inst.chat.return_value = _make_mock_response("")
        mock_client.return_value = mock_inst

        llm = OllamaLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")

    @mock.patch("mem0.llms.ollama.Client")
    def test_custom_base_url(self, mock_client):
        cfg = OllamaConfig(model="llama3.1:70b", ollama_base_url="http://localhost:11440")
        OllamaLLM(cfg)
        mock_client.assert_called_once_with(host="http://localhost:11440")
