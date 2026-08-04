"""Tests for ``mem0.llms.base.LLMBase`` helper methods."""

from unittest import TestCase, mock

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class DummyLLM(LLMBase):
    """Concrete subclass that exposes protected helpers for testing."""

    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        return "dummy"


class TestLLMBaseHelpers(TestCase):
    """Tests for _is_reasoning_model and _uses_max_completion_tokens."""

    def _make_llm(self, model, **overrides):
        cfg = BaseLlmConfig(model=model, **overrides)
        return DummyLLM(cfg)

    # -- _is_reasoning_model --

    def test_reasoning_o1(self):
        llm = self._make_llm("o1")
        self.assertTrue(llm._is_reasoning_model("o1"))

    def test_reasoning_o3_mini(self):
        llm = self._make_llm("o3-mini")
        self.assertTrue(llm._is_reasoning_model("o3-mini"))

    def test_reasoning_gpt5(self):
        llm = self._make_llm("gpt-5")
        self.assertTrue(llm._is_reasoning_model("gpt-5"))

    def test_reasoning_gpt5o(self):
        llm = self._make_llm("gpt-5o")
        self.assertTrue(llm._is_reasoning_model("gpt-5o"))

    def test_non_reasoning_gpt4(self):
        llm = self._make_llm("gpt-4o")
        self.assertFalse(llm._is_reasoning_model("gpt-4o"))

    def test_explicit_true(self):
        llm = self._make_llm("my-custom-model", is_reasoning_model=True)
        self.assertTrue(llm._is_reasoning_model("my-custom-model"))

    def test_explicit_false(self):
        llm = self._make_llm("o1", is_reasoning_model=False)
        self.assertFalse(llm._is_reasoning_model("o1"))

    def test_reasoning_with_prefix(self):
        llm = self._make_llm("openai/o3-mini")
        self.assertTrue(llm._is_reasoning_model("openai/o3-mini"))

    # -- _uses_max_completion_tokens --

    def test_uses_max_completion_gpt5(self):
        llm = self._make_llm("gpt-5.4-mini")
        self.assertTrue(llm._uses_max_completion_tokens("gpt-5.4-mini"))

    def test_uses_max_completion_gpt4(self):
        llm = self._make_llm("gpt-4o")
        self.assertFalse(llm._uses_max_completion_tokens("gpt-4o"))

    def test_uses_max_completion_with_prefix(self):
        llm = self._make_llm("openai/gpt-5.5")
        self.assertTrue(llm._uses_max_completion_tokens("openai/gpt-5.5"))

    # -- _get_supported_params --

    def test_reasoning_params_filter(self):
        llm = self._make_llm("o1")
        params = llm._get_supported_params(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
            max_tokens=100,
        )
        self.assertIn("messages", params)
        self.assertNotIn("temperature", params)
        self.assertNotIn("max_tokens", params)

    def test_reasoning_params_include_reasoning_effort(self):
        llm = self._make_llm("o1", reasoning_effort="high")
        params = llm._get_supported_params(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
        )
        self.assertIn("reasoning_effort", params)
        self.assertEqual(params["reasoning_effort"], "high")

    def test_non_reasoning_params_include_temperature(self):
        llm = self._make_llm("gpt-4o")
        params = llm._get_supported_params(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.5,
        )
        self.assertIn("temperature", params)
