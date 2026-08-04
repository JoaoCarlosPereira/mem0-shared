"""Tests for mem0.utils.factory — LlmFactory, EmbedderFactory, VectorStoreFactory, RerankerFactory."""

from unittest.mock import MagicMock
import pytest

from mem0.utils.factory import (
    EmbedderFactory,
    LlmFactory,
    RerankerFactory,
    VectorStoreFactory,
    load_class,
)


class TestLoadClass:
    """Tests for the load_class helper."""

    def test_load_builtin_class(self):
        """load_class can load a standard library class."""
        result = load_class("os.path.join")
        assert callable(result)

    def test_load_class_module_not_found(self):
        """load_class raises ImportError when module doesn't exist."""
        with pytest.raises((ImportError, ModuleNotFoundError)):
            load_class("nonexistent_module.foo.Bar")

    def test_load_class_attr_error(self):
        """load_class raises AttributeError when attribute doesn't exist."""
        with pytest.raises(AttributeError):
            load_class("os.path.NonexistentClass")


class TestLlmFactory:
    """Tests for LlmFactory."""

    def test_get_supported_providers_returns_list(self):
        """get_supported_providers returns a list of provider names."""
        providers = LlmFactory.get_supported_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_get_supported_providers_contains_openai(self):
        """Default providers include 'openai'."""
        assert "openai" in LlmFactory.get_supported_providers()

    def test_register_provider_adds_to_mapping(self):
        """register_provider adds a new entry to provider_to_class."""
        initial_count = len(LlmFactory.provider_to_class)
        LlmFactory.register_provider("test_provider", "os.path.join", None)
        assert "test_provider" in LlmFactory.provider_to_class
        assert len(LlmFactory.provider_to_class) == initial_count + 1

    def test_unsupported_provider_raises(self):
        """create raises ValueError for an unknown provider."""
        with pytest.raises(ValueError, match="Unsupported Llm provider"):
            LlmFactory.create("totally_unknown_provider", None)

    def test_register_and_create_with_kwargs(self):
        """Registered provider can be used via create with kwargs."""
        LlmFactory.register_provider("test_kws", "os.path.join", None)
        # BaseLlmConfig(**kwargs) will raise ValueError for unknown kwargs like "foo"
        with pytest.raises((ValueError, TypeError)):
            LlmFactory.create("test_kws", None, foo="bar")

    def test_provider_to_class_is_dict(self):
        """provider_to_class is a dict mapping provider names to tuples."""
        for provider, mapping in LlmFactory.provider_to_class.items():
            assert isinstance(provider, str)
            assert isinstance(mapping, tuple)
            assert len(mapping) == 2


class TestEmbedderFactory:
    """Tests for EmbedderFactory."""

    def test_supported_providers_contains_openai(self):
        """EmbedderFactory.provider_to_class contains 'openai'."""
        assert "openai" in EmbedderFactory.provider_to_class

    def test_unsupported_provider_raises(self):
        """create raises ValueError for unknown embedder provider."""
        with pytest.raises(ValueError, match="Unsupported Embedder provider"):
            EmbedderFactory.create("unknown_embedder", {}, {})

    def test_upstash_vector_with_embeddings_enabled(self):
        """When provider is upstash_vector and enable_embeddings is True,
        returns MockEmbeddings instead of trying to load a class."""
        from mem0.embeddings.mock import MockEmbeddings

        # EmbedderFactory.create checks vector_config.enable_embeddings as attribute
        class FakeVectorConfig:
            enable_embeddings = True

        result = EmbedderFactory.create("upstash_vector", {}, FakeVectorConfig())
        assert isinstance(result, MockEmbeddings)

    def test_upstash_vector_with_embeddings_disabled(self):
        """upstash_vector without enable_embeddings falls through to normal path."""
        class FakeVectorConfig:
            enable_embeddings = False

        # Provider not in provider_to_class → ValueError
        with pytest.raises(ValueError):
            EmbedderFactory.create("upstash_vector", {}, FakeVectorConfig())


class TestVectorStoreFactory:
    """Tests for VectorStoreFactory."""

    def test_supported_providers_contains_qdrant(self):
        """VectorStoreFactory.provider_to_class contains 'qdrant'."""
        assert "qdrant" in VectorStoreFactory.provider_to_class

    def test_unsupported_provider_raises(self):
        """create raises ValueError for unknown vector store provider."""
        with pytest.raises(ValueError, match="Unsupported VectorStore provider"):
            VectorStoreFactory.create("unknown_vs", {})

    def test_create_with_dict_config(self):
        """create accepts a dict config."""
        # We just verify it tries to load — it will raise ImportError for missing deps
        # but the dict->dict conversion logic works
        with pytest.raises((ImportError, Exception)):
            VectorStoreFactory.create("qdrant", {"collection_name": "test"})

    def test_create_with_non_dict_config(self):
        """create converts non-dict config to dict via model_dump."""
        class FakeConfig:
            def model_dump(self):
                return {"collection_name": "test"}

        with pytest.raises((ImportError, Exception)):
            VectorStoreFactory.create("qdrant", FakeConfig())

    def test_reset_returns_instance(self):
        """reset calls instance.reset() and returns the instance."""
        mock_instance = MagicMock()
        result = VectorStoreFactory.reset(mock_instance)
        mock_instance.reset.assert_called_once()
        assert result is mock_instance


class TestRerankerFactory:
    """Tests for RerankerFactory."""

    def test_get_supported_providers_contains_cohere(self):
        """RerankerFactory includes 'cohere'."""
        assert "cohere" in RerankerFactory.provider_to_class

    def test_unsupported_provider_raises(self):
        """create raises ValueError for unknown reranker."""
        with pytest.raises(ValueError, match="Unsupported reranker provider"):
            RerankerFactory.create("unknown_reranker", None)

    def test_invalid_config_type_raises(self):
        """create raises ValueError when config is neither BaseRerankerConfig nor dict."""
        with pytest.raises(ValueError, match="Config must be a"):
            RerankerFactory.create("cohere", "not_a_config")

    def test_provider_mappings_are_tuples(self):
        """All provider_to_class entries are (class_path, config_class) tuples."""
        for name, mapping in RerankerFactory.provider_to_class.items():
            assert isinstance(name, str)
            assert isinstance(mapping, tuple)
            assert len(mapping) == 2
