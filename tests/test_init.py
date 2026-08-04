"""Smoke tests for mem0.__init__.py — import/export of Memory, AsyncMemory, MemoryClient, AsyncMemoryClient."""

import pytest


class TestInitImports:
    """Tests for the top-level mem0 package exports."""

    def test_memory_importable(self):
        """Memory class can be imported from mem0."""
        from mem0 import Memory
        assert Memory is not None

    def test_async_memory_importable(self):
        """AsyncMemory class can be imported from mem0."""
        from mem0 import AsyncMemory
        assert AsyncMemory is not None

    def test_memory_client_importable(self):
        """MemoryClient class can be imported from mem0."""
        from mem0 import MemoryClient
        assert MemoryClient is not None

    def test_async_memory_client_importable(self):
        """AsyncMemoryClient class can be imported from mem0."""
        from mem0 import AsyncMemoryClient
        assert AsyncMemoryClient is not None

    def test_version_exists(self):
        """mem0.__version__ is set."""
        import mem0
        assert hasattr(mem0, "__version__")
        assert isinstance(mem0.__version__, str)
        assert len(mem0.__version__) > 0
