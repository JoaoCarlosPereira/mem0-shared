"""Tests for ``mem0.llms.configs`` and provider-specific config classes."""

from unittest import TestCase

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.deepseek import DeepSeekConfig
from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.configs.llms.ollama import OllamaConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.configs.llms.vllm import VllmConfig
from mem0.configs.llms.xai import XAIConfig
from mem0.llms.configs import LlmConfig


# -- LlmConfig --

class TestLlmConfig(TestCase):
    """Tests for ``mem0.llms.configs.LlmConfig``."""

    def test_valid_provider(self):
        cfg = LlmConfig(provider="openai", config={"model": "gpt-4o"})
        self.assertEqual(cfg.provider, "openai")

    def test_unsupported_provider_raises(self):
        # The field_validator on `config` fires when both provider and config are set.
        with self.assertRaises(ValueError):
            LlmConfig(provider="unsupported-provider", config={})

    def test_default_provider(self):
        cfg = LlmConfig()
        self.assertEqual(cfg.provider, "openai")

    def test_empty_config_default(self):
        cfg = LlmConfig(provider="ollama")
        self.assertEqual(cfg.config, {})


# -- Provider configs --

class TestBaseLlmConfig(TestCase):
    """Tests for ``BaseLlmConfig``."""

    def test_defaults(self):
        cfg = BaseLlmConfig()
        self.assertEqual(cfg.temperature, 0.1)
        self.assertEqual(cfg.max_tokens, 2000)
        self.assertEqual(cfg.top_p, 0.1)
        self.assertEqual(cfg.top_k, 1)
        self.assertFalse(cfg.enable_vision)
        self.assertIsNone(cfg.api_key)
        self.assertIsNone(cfg.model)

    def test_custom_values(self):
        cfg = BaseLlmConfig(
            model="gpt-4o",
            temperature=0.5,
            api_key="sk-test",
            max_tokens=500,
            top_p=0.9,
            top_k=50,
            enable_vision=True,
        )
        self.assertEqual(cfg.model, "gpt-4o")
        self.assertEqual(cfg.temperature, 0.5)
        self.assertEqual(cfg.api_key, "sk-test")
        self.assertEqual(cfg.max_tokens, 500)
        self.assertEqual(cfg.top_p, 0.9)
        self.assertEqual(cfg.top_k, 50)
        self.assertTrue(cfg.enable_vision)


class TestOpenAIConfig(TestCase):
    def test_defaults(self):
        cfg = OpenAIConfig()
        self.assertEqual(cfg.model, None)
        self.assertIsNone(cfg.openai_base_url)
        self.assertIsNone(cfg.models)
        self.assertEqual(cfg.route, "fallback")
        self.assertIsNone(cfg.store)

    def test_custom(self):
        cfg = OpenAIConfig(
            model="gpt-4o",
            openai_base_url="https://custom.openai.com/v1",
            models=["gpt-4o", "gpt-3.5"],
            store=True,
        )
        self.assertEqual(cfg.openai_base_url, "https://custom.openai.com/v1")
        self.assertEqual(cfg.models, ["gpt-4o", "gpt-3.5"])
        self.assertTrue(cfg.store)


class TestAnthropicConfig(TestCase):
    def test_defaults(self):
        cfg = AnthropicConfig()
        self.assertIsNone(cfg.model)
        self.assertIsNone(cfg.anthropic_base_url)


class TestDeepSeekConfig(TestCase):
    def test_defaults(self):
        cfg = DeepSeekConfig()
        self.assertIsNone(cfg.model)
        self.assertIsNone(cfg.deepseek_base_url)


class TestAWSBedrockConfig(TestCase):
    def test_defaults(self):
        cfg = AWSBedrockConfig()
        self.assertEqual(cfg.aws_region, "us-west-2")
        self.assertEqual(cfg.get_model_config()["temperature"], 0.1)
        self.assertEqual(cfg.get_model_config()["max_tokens"], 2000)

    def test_get_model_config_excludes_none_top_p(self):
        cfg = AWSBedrockConfig(top_p=None)
        mc = cfg.get_model_config()
        self.assertNotIn("top_p", mc)

    def test_get_model_config_includes_top_p_when_set(self):
        cfg = AWSBedrockConfig(top_p=0.8)
        mc = cfg.get_model_config()
        self.assertEqual(mc["top_p"], 0.8)

    def test_get_aws_config(self):
        cfg = AWSBedrockConfig(
            aws_access_key_id="AKIA",
            aws_secret_access_key="secret",
            aws_region="eu-west-1",
        )
        ac = cfg.get_aws_config()
        self.assertEqual(ac["region_name"], "eu-west-1")
        self.assertEqual(ac["aws_access_key_id"], "AKIA")


class TestAzureOpenAIConfig(TestCase):
    def test_defaults(self):
        cfg = AzureOpenAIConfig()
        self.assertIsNotNone(cfg.azure_kwargs)


class TestLMStudioConfig(TestCase):
    def test_default_base_url(self):
        cfg = LMStudioConfig()
        self.assertEqual(cfg.lmstudio_base_url, "http://localhost:1234/v1")


class TestOllamaConfig(TestCase):
    def test_defaults(self):
        cfg = OllamaConfig()
        self.assertIsNone(cfg.ollama_base_url)


class TestVllmConfig(TestCase):
    def test_default_base_url(self):
        cfg = VllmConfig()
        self.assertEqual(cfg.vllm_base_url, "http://localhost:8000/v1")


class TestXAIConfig(TestCase):
    def test_defaults(self):
        cfg = XAIConfig()
        self.assertIsNone(cfg.xai_base_url)
