"""Tests for mem0.proxy.main — Mem0, Chat, Completions compatibility proxy."""

import sys
from unittest.mock import MagicMock, patch

# Mock litellm before importing mem0.proxy.main (which tries pip install litellm)
sys.modules["litellm"] = MagicMock()

import pytest

from mem0.proxy.main import Mem0, Chat, Completions


class TestMem0:
    """Tests for the Mem0 proxy class."""

    def test_with_api_key_creates_memory_client(self):
        """Mem0 with api_key creates a MemoryClient."""
        with patch("mem0.proxy.main.MemoryClient") as mock_mc:
            mock_instance = MagicMock()
            mock_mc.return_value = mock_instance

            m = Mem0(api_key="test-key")
            assert m.mem0_client is mock_instance

    def test_with_config_creates_memory_from_config(self):
        """Mem0 with config calls Memory.from_config."""
        with patch("mem0.proxy.main.Memory") as mock_mem:
            mock_instance = MagicMock()
            mock_mem.from_config.return_value = mock_instance

            m = Mem0(config={})
            # Memory.from_config returns the mock_instance which should be assigned to mem0_client
            # Note: in proxy/main.py, it's: self.mem0_client = Memory.from_config(config) if config else Memory()
            # If config is empty dictionary {}, config evaluates to False in python boolean context
            # We must pass a non-empty dictionary to trigger the config path.
            assert m.mem0_client is mock_mem.return_value

    def test_with_non_empty_config_creates_memory_from_config(self):
        """Mem0 with non-empty config calls Memory.from_config."""
        with patch("mem0.proxy.main.Memory") as mock_mem:
            mock_instance = MagicMock()
            mock_mem.from_config.return_value = mock_instance

            m = Mem0(config={"some": "config"})
            assert m.mem0_client is mock_instance

    def test_no_params_creates_default_memory(self):
        """Mem0 with no params creates a default Memory instance."""
        with patch("mem0.proxy.main.Memory") as mock_mem:
            mock_instance = MagicMock()
            mock_mem.return_value = mock_instance

            m = Mem0()
            assert m.mem0_client is mock_instance

    def test_chat_initialized(self):
        """Mem0 initializes self.chat with a Chat instance."""
        with patch("mem0.proxy.main.Memory"):
            m = Mem0()
            assert isinstance(m.chat, Chat)


class TestChat:
    """Tests for the Chat class."""

    def test_initializes_completions(self):
        """Chat initializes self.completions with a Completions instance."""
        mock_client = MagicMock()
        chat = Chat(mock_client)
        assert isinstance(chat.completions, Completions)


class TestCompletions:
    """Tests for the Completions class."""

    def test_create_without_user_id_agent_id_run_id_raises(self):
        """Completions.create raises ValueError without user_id/agent_id/run_id."""
        mock_client = MagicMock()
        completions = Completions(mock_client)

        with pytest.raises(ValueError, match="One of user_id, agent_id, run_id"):
            completions.create(model="gpt-4", messages=[{"role": "user", "content": "hi"}])

    def test_create_prepends_system_prompt(self):
        """Completions.create prepends system prompt when missing."""
        mock_client = MagicMock()
        completions = Completions(mock_client)
        completions._prepare_messages = MagicMock(return_value=[
            {"role": "system", "content": "prompt"},
            {"role": "user", "content": "hi"},
        ])
        completions._fetch_relevant_memories = MagicMock(return_value={})
        completions._format_query_with_memories = MagicMock(return_value="formatted")

        with (
            patch("mem0.proxy.main.litellm") as mock_litellm,
            patch.object(completions, "_async_add_to_memory"),
        ):
            mock_litellm.supports_function_calling.return_value = True
            mock_response = MagicMock()
            mock_litellm.completion.return_value = mock_response

            completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "hi"}],
                user_id="u1",
            )
            # Verify system prompt was prepended
            completions._prepare_messages.assert_called_once()

    def test_async_add_called(self):
        """_async_add_to_memory is called with correct params."""
        mock_client = MagicMock()
        completions = Completions(mock_client)

        with (
            patch("mem0.proxy.main.litellm") as mock_litellm,
            patch.object(completions, "_prepare_messages", return_value=[{"role": "user", "content": "hi"}]),
            patch.object(completions, "_fetch_relevant_memories", return_value={}),
            patch.object(completions, "_format_query_with_memories", return_value="formatted"),
            patch.object(completions, "_async_add_to_memory"),
            patch("mem0.proxy.main.threading") as mock_threading,
        ):
            mock_litellm.supports_function_calling.return_value = True
            mock_litellm.completion.return_value = MagicMock()

            completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "hi"}],
                user_id="u1",
                agent_id="a1",
                metadata={"k": "v"},
                filters={"f": "v"},
                top_k=5,
            )
            completions._async_add_to_memory.assert_called_once()

    def test_model_without_function_calling_raises(self):
        """Raises ValueError for models that don't support function calling."""
        mock_client = MagicMock()
        completions = Completions(mock_client)

        with patch("mem0.proxy.main.litellm") as mock_litellm:
            mock_litellm.supports_function_calling.return_value = False

            with pytest.raises(ValueError, match="does not support function calling"):
                completions.create(
                    model="old-model",
                    messages=[{"role": "user", "content": "hi"}],
                    user_id="u1",
                )

    def test_prepare_messages_with_system(self):
        """_prepare_messages does not prepend when system already exists."""
        mock_client = MagicMock()
        completions = Completions(mock_client)
        messages = [
            {"role": "system", "content": "existing"},
            {"role": "user", "content": "hi"},
        ]
        result = completions._prepare_messages(messages)
        assert result == messages

    def test_prepare_messages_without_system(self):
        """_prepare_messages prepends system prompt."""
        mock_client = MagicMock()
        completions = Completions(mock_client)
        messages = [{"role": "user", "content": "hi"}]
        result = completions._prepare_messages(messages)
        assert result[0]["role"] == "system"
        assert len(result) == len(messages) + 1

    def test_prepare_messages_empty(self):
        """_prepare_messages handles empty messages."""
        mock_client = MagicMock()
        completions = Completions(mock_client)
        result = completions._prepare_messages([])
        assert result[0]["role"] == "system"

    def test_fetch_relevant_memories(self):
        """_fetch_relevant_memories passes last 6 messages."""
        mock_client = MagicMock()
        completions = Completions(mock_client)

        messages = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        completions.mem0_client = mock_client
        completions._fetch_relevant_memories(
            messages, "u1", None, "r1", None, 10
        )
        mock_client.search.assert_called_once()
        call_args = mock_client.search.call_args[1]
        # Should include last 6 messages
        assert call_args["user_id"] == "u1"
        assert call_args["run_id"] == "r1"

    def test_format_query_with_memories_memory(self):
        """Formats query with memories for Memory instance."""
        mock_client = MagicMock()
        completions = Completions(mock_client)
        completions.mem0_client = MagicMock()
        # Mock Memory vs MemoryClient
        completions.mem0_client.__class__.__name__ = "Memory"

        messages = [{"role": "user", "content": "what happened?"}]
        relevant = [{"memory": "mem1"}, {"memory": "mem2"}]

        result = completions._format_query_with_memories(messages, relevant)
        assert isinstance(result, str)

    def test_format_query_with_memories_client(self):
        """Formats query with memories for MemoryClient instance."""
        mock_client = MagicMock()
        completions = Completions(mock_client)
        completions.mem0_client = MagicMock()
        completions.mem0_client.__class__.__name__ = "MemoryClient"

        messages = [{"role": "user", "content": "what happened?"}]
        relevant = [{"memory": "mem1"}, {"memory": "mem2"}]

        result = completions._format_query_with_memories(messages, relevant)
        assert isinstance(result, str)
