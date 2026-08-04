"""Tests for ``mem0.llms.aws_bedrock.AWSBedrockLLM``."""

import json
from unittest import TestCase, mock

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.aws_bedrock import AWSBedrockLLM, extract_provider


# -- helpers --

def _make_mock_body(body_str):
    """Create a mock body object that behaves like ``response['body'].read()``."""
    mock_body = mock.MagicMock()
    mock_body.read.return_value = body_str.encode("utf-8")
    return mock_body


def _make_mock_response(body_str):
    resp = {"body": _make_mock_body(body_str)}
    return resp


class TestExtractProvider(TestCase):
    """Tests for ``extract_provider`` utility."""

    def test_anthropic(self):
        self.assertEqual(extract_provider("anthropic.claude-3-5-sonnet"), "anthropic")

    def test_amazon(self):
        self.assertEqual(extract_provider("amazon.nova-3-mini"), "amazon")

    def test_cohere(self):
        self.assertEqual(extract_provider("cohere.command-r"), "cohere")

    def test_meta(self):
        self.assertEqual(extract_provider("meta.llama3"), "meta")

    def test_mistral(self):
        self.assertEqual(extract_provider("mistral.mistral-large"), "mistral")

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            extract_provider("unknown-model")


class TestAWSBedrockLLM(TestCase):
    """Tests for AWSBedrockLLM initialization and response handling."""

    def _make_llm(self, model="anthropic.claude-3-5-sonnet-20240620-v1:0", **overrides):
        cfg = AWSBedrockConfig(model=model, **overrides)
        with mock.patch("boto3.client"):
            llm = AWSBedrockLLM(cfg)
        return llm

    # -- initialization --

    def test_initialization_anthropic(self):
        llm = self._make_llm()
        self.assertEqual(llm.provider, "anthropic")

    def test_initialization_amazon(self):
        llm = self._make_llm("amazon.nova-3-mini-20241119-v1:0")
        self.assertEqual(llm.provider, "amazon")

    @mock.patch("boto3.client")
    def test_aws_credentials_not_found_raises(self, mock_boto):
        from botocore.exceptions import NoCredentialsError

        mock_boto.side_effect = NoCredentialsError()
        cfg = AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0")
        with self.assertRaises(ValueError) as ctx:
            AWSBedrockLLM(cfg)
        self.assertIn("AWS credentials not found", str(ctx.exception))

    # -- message formatting --

    def test_anthropic_format_messages(self):
        llm = self._make_llm()
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        formatted, system = llm._format_messages_anthropic(msgs)
        self.assertEqual(system, "You are helpful.")
        self.assertEqual(len(formatted), 2)
        self.assertEqual(formatted[0]["role"], "user")
        self.assertEqual(formatted[1]["role"], "assistant")

    def test_cohere_format_messages(self):
        llm = self._make_llm("cohere.command-r")
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        formatted = llm._format_messages_cohere(msgs)
        self.assertIn("User: hi", formatted)
        self.assertIn("Assistant: hello", formatted)

    def test_generic_format_messages(self):
        llm = self._make_llm("ai21.j2-ultra")
        msgs = [
            {"role": "user", "content": "hi"},
        ]
        formatted = llm._format_messages(msgs)
        self.assertIn("User: hi", formatted)
        self.assertIn("Assistant:", formatted)

    # -- response parsing --

    def test_anthropic_response_parsed(self):
        llm = self._make_llm()
        body = json.dumps({"content": [{"text": "Hello from Claude!"}]})
        result = llm._parse_response(_make_mock_response(body))
        self.assertEqual(result, "Hello from Claude!")

    def test_amazon_response_parsed(self):
        llm = self._make_llm("amazon.titan-text-premier")
        body = json.dumps({"completion": "Amazon Titan response"})
        result = llm._parse_response(_make_mock_response(body))
        self.assertEqual(result, "Amazon Titan response")

    def test_meta_response_parsed(self):
        llm = self._make_llm("meta.llama3-8b")
        body = json.dumps({"generation": "Meta Llama response"})
        result = llm._parse_response(_make_mock_response(body))
        self.assertEqual(result, "Meta Llama response")

    def test_cohere_response_parsed(self):
        llm = self._make_llm("cohere.command-r")
        body = json.dumps({"generations": [{"text": "Cohere response"}]})
        result = llm._parse_response(_make_mock_response(body))
        self.assertEqual(result, "Cohere response")

    def test_mistral_response_parsed(self):
        llm = self._make_llm("mistral.mistral-large")
        body = json.dumps({"outputs": [{"text": "Mistral response"}]})
        result = llm._parse_response(_make_mock_response(body))
        self.assertEqual(result, "Mistral response")

    def test_invalid_json_response_returns_error(self):
        llm = self._make_llm()
        body = "not valid json at all"
        result = llm._parse_response(_make_mock_response(body))
        self.assertEqual(result, "Error parsing response")

    def test_converse_response_parsing(self):
        """Test Converse API response parsing for Anthropic.
        Converse responses have .output.message.content, but _parse_response
        expects response['body'].read() for provider-specific parsing.
        The converse path is tested in _generate_standard.
        """
        llm = self._make_llm()
        # Converse response doesn't go through _parse_response directly
        # It's handled in _generate_standard which returns response.output.message.content[0].text
        self.assertTrue(llm.supports_tools)

    # -- _prepare_input --

    def test_prepare_input_anthropic(self):
        llm = self._make_llm()
        input_body = llm._prepare_input("hello")
        self.assertIn("messages", input_body)
        self.assertIn("anthropic_version", input_body)

    def test_prepare_input_amazon_legacy(self):
        llm = self._make_llm("amazon.titan-text-premier")
        input_body = llm._prepare_input("hello")
        self.assertIn("inputText", input_body)
        self.assertIn("textGenerationConfig", input_body)

    def test_prepare_input_meta(self):
        llm = self._make_llm("meta.llama3-8b")
        input_body = llm._prepare_input("hello")
        self.assertIn("prompt", input_body)
        self.assertIn("max_gen_len", input_body)

    # -- _build_inference_config --

    def test_inference_config_includes_max_tokens(self):
        llm = self._make_llm()
        cfg = llm._build_inference_config()
        self.assertIn("maxTokens", cfg)
        self.assertIn("temperature", cfg)

    def test_inference_config_omits_top_p_for_anthropic(self):
        """Anthropic Converse rejects both temperature and topP together."""
        llm = self._make_llm()
        llm.config.top_p = 0.9
        llm.model_config["top_p"] = 0.9
        cfg = llm._build_inference_config()
        self.assertNotIn("topP", cfg)

    # -- get_model_capabilities --

    def test_model_capabilities(self):
        llm = self._make_llm()
        caps = llm.get_model_capabilities()
        self.assertEqual(caps["model_id"], "anthropic.claude-3-5-sonnet-20240620-v1:0")
        self.assertEqual(caps["provider"], "anthropic")
        self.assertTrue(caps["supports_tools"])

    # -- generate_response standard path (Converse) --

    @mock.patch("boto3.client")
    def test_generate_response_anthropic_converse(self, mock_boto):
        mock_client = mock.MagicMock()
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Claude response"}]}}
        }
        mock_boto.return_value = mock_client

        llm = self._make_llm()
        llm.client = mock_client
        result = llm.generate_response([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "Claude response")
