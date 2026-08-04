"""Tests for ``mem0.llms.azure_openai_structured.AzureOpenAIStructuredLLM``."""

import sys
from unittest import TestCase, mock

# Mock optional dependencies before importing the module.
sys.modules["azure"] = mock.MagicMock()
sys.modules["azure.identity"] = mock.MagicMock()
sys.modules["azure.identity.DefaultAzureCredential"] = mock.MagicMock()
sys.modules["azure.identity.get_bearer_token_provider"] = mock.MagicMock()

from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.llms.azure_openai_structured import AzureOpenAIStructuredLLM


def _make_mock_response(content="Azure structured response"):
    msg = mock.MagicMock()
    msg.content = content
    msg.tool_calls = []
    choice = mock.MagicMock()
    choice.message = msg
    resp = mock.MagicMock()
    resp.choices = [choice]
    return resp


def _make_azure_config(model="gpt-5-mini", **overrides):
    """Build an AzureOpenAIConfig with the given model and optional azure kwargs."""
    azure_kwargs = {
        "azure_deployment": "gpt-5-deployment",
        "azure_endpoint": "https://openai.azure.com",
        "api_version": "2024-02-01",
    }
    azure_kwargs.update(overrides)
    return AzureOpenAIConfig(
        model=model,
        api_key="azure-key",
        azure_kwargs=azure_kwargs,
    )


class TestAzureOpenAIStructuredLLM(TestCase):
    """Tests for AzureOpenAIStructuredLLM initialization and response handling."""

    def setUp(self):
        self.cfg = _make_azure_config("gpt-5-mini")

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_initialization(self, mock_azure):
        llm = AzureOpenAIStructuredLLM(self.cfg)
        mock_azure.assert_called_once()
        self.assertEqual(llm.config.model, "gpt-5-mini")

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_default_model(self, mock_azure):
        llm = AzureOpenAIStructuredLLM(_make_azure_config())
        self.assertEqual(llm.config.model, "gpt-5-mini")

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_text_completion(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response("Hello!")
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Hello!")

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_tools_passed(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(self.cfg)
        tools = [{"type": "function", "function": {"name": "search", "parameters": {}}}]
        llm.generate_response([{"role": "user", "content": "hi"}], tools=tools)
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertIn("tools", call_kwargs)

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_response_format_passed(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(self.cfg)
        llm.generate_response(
            [{"role": "user", "content": "hi"}],
            response_format={"type": "json_object"},
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["response_format"], {"type": "json_object"})

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_reasoning_model_omits_temperature(self, mock_azure):
        """Reasoning models (o1, o3, gpt-5) should not receive temperature/top_p."""
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(_make_azure_config("gpt-5o-mini"))
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("temperature", call_kwargs)
        self.assertNotIn("top_p", call_kwargs)
        self.assertIn("max_completion_tokens", call_kwargs)

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_non_reasoning_model_includes_temperature(self, mock_azure):
        cfg = _make_azure_config("gpt-4o")
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertIn("temperature", call_kwargs)
        self.assertIn("top_p", call_kwargs)
        self.assertIn("max_tokens", call_kwargs)
        self.assertNotIn("max_completion_tokens", call_kwargs)

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
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

        llm = AzureOpenAIStructuredLLM(self.cfg)
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "")

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_user_prompt_replaces_assistant_with_ai(self, mock_azure):
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(self.cfg)
        llm.generate_response([{"role": "user", "content": "say assistant"}])
        messages_arg = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertNotIn("assistant", messages_arg[-1]["content"])
        self.assertIn("ai", messages_arg[-1]["content"])

    @mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    def test_reasoning_model_with_reasoning_effort(self, mock_azure):
        cfg = _make_azure_config("o1")
        cfg.reasoning_effort = "high"
        mock_client = mock.MagicMock()
        mock_client.chat.completions.create.return_value = _make_mock_response()
        mock_azure.return_value = mock_client

        llm = AzureOpenAIStructuredLLM(cfg)
        llm.generate_response([{"role": "user", "content": "hi"}])
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["reasoning_effort"], "high")
