"""Tests for ``mem0.llms.azure_openai.AzureOpenAILLM``."""

import sys
from unittest import TestCase, mock

# Mock optional dependencies before importing the module.
sys.modules["azure"] = mock.MagicMock()
sys.modules["azure.identity"] = mock.MagicMock()
sys.modules["azure.identity.DefaultAzureCredential"] = mock.MagicMock()
sys.modules["azure.identity.get_bearer_token_provider"] = mock.MagicMock()

from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.llms.azure_openai import AzureOpenAILLM


def _make_mock_response(content="Azure response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


class TestAzureOpenAILLM(TestCase):
    """Tests for AzureOpenAILLM initialization and response handling."""

    def setUp(self):
        self.cfg = AzureOpenAIConfig(
            model="gpt-4",
            api_key="azure-key",
            azure_kwargs={
                "azure_deployment": "gpt-4-deployment",
                "azure_endpoint": "https://openai.azure.com",
                "api_version": "2024-02-01",
            },
        )

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_initialization(self, mock_azure):
        AzureOpenAILLM(self.cfg)
        mock_azure.assert_called_once()

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_default_model(self, mock_azure):
        cfg = AzureOpenAIConfig(api_key="azure-key")
        llm = AzureOpenAILLM(cfg)
        # AzureOpenAILLM defaults to "gpt-5-mini"
        self.assertEqual(llm.config.model, "gpt-5-mini")

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_text_completion(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_azure.return_value = mock_client

        llm = AzureOpenAILLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_tools_passed(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAILLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        llm.generate_response([{"role": "user", "content": "hi"}], tools=tools)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertIn("tools", call_kwargs)

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_response_format_passed(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAILLM(self.cfg)
        llm.generate_response(
            [{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_empty_response(self, mock_azure):
        msg = mock.MagicMock()
        msg.content = ""
        msg.tool_calls = []
        choice = mock.MagicMock()
        choice.message = msg
        resp = mock.MagicMock()
        resp.choices = [choice]

        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = resp
        mock_azure.return_value = mock_client

        llm = AzureOpenAILLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")

    @mock.patch("mem0.llms.azure_openai.AzureOpenAI")
    def test_user_prompt_replaces_assistant_with_ai(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAILLM(self.cfg)
        llm.generate_response([{"role": "user", "content": "say assistant"}])
        messages_arg = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertNotIn("assistant", messages_arg[-1]["content"])
        self.assertIn("ai", messages_arg[-1]["content"])
