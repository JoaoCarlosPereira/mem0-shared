"""Tests for mem0.memory.base.MemoryBase abstract class."""

import pytest

from mem0.memory.base import MemoryBase


class ConcreteMemory(MemoryBase):
    """Minimal concrete implementation of MemoryBase for testing."""

    def __init__(self):
        self._store = {}
        self._history = {}

    def get(self, memory_id):
        return self._store.get(memory_id)

    def get_all(self):
        return list(self._store.values())

    def update(self, memory_id, data):
        if memory_id in self._store:
            self._store[memory_id] = data
            return {"status": "ok"}
        return {"status": "not_found"}

    def delete(self, memory_id):
        if memory_id in self._store:
            del self._store[memory_id]
            return {"status": "ok"}
        return {"status": "not_found"}

    def history(self, memory_id):
        return list(self._history.get(memory_id, []))


class TestMemoryBaseAbstract:
    """MemoryBase cannot be instantiated directly because it has abstract methods."""

    def test_cannot_instantiate_abstract_base(self):
        with pytest.raises(TypeError):
            MemoryBase()

    def test_subclass_without_implementing_abstract_methods_raises(self):
        class IncompleteMemory(MemoryBase):
            pass

        with pytest.raises(TypeError):
            IncompleteMemory()

    def test_subclass_implementing_all_abstract_methods_instantiates(self):
        # Should not raise
        inst = ConcreteMemory()
        assert inst is not None

    def test_memory_base_has_abstract_methods(self):
        # Verify the expected abstract methods are defined
        abstract_methods = MemoryBase.__abstractmethods__
        assert "get" in abstract_methods
        assert "get_all" in abstract_methods
        assert "update" in abstract_methods
        assert "delete" in abstract_methods
        assert "history" in abstract_methods

    def test_memory_base_has_no_other_abstract_methods(self):
        abstract_methods = MemoryBase.__abstractmethods__
        expected = {"get", "get_all", "update", "delete", "history"}
        assert abstract_methods == expected


class TestConcreteMemory:
    """Test the concrete implementation for behavioral correctness."""

    @pytest.fixture
    def memory(self):
        return ConcreteMemory()

    # -- get --

    def test_get_existing_memory(self, memory):
        memory._store["m1"] = {"text": "hello"}
        result = memory.get("m1")
        assert result == {"text": "hello"}

    def test_get_nonexistent_memory(self, memory):
        result = memory.get("nonexistent")
        assert result is None

    # -- get_all --

    def test_get_all_empty(self, memory):
        assert memory.get_all() == []

    def test_get_all_single(self, memory):
        memory._store["m1"] = {"text": "hello"}
        result = memory.get_all()
        assert len(result) == 1
        assert result[0] == {"text": "hello"}

    def test_get_all_multiple(self, memory):
        memory._store["m1"] = {"text": "hello"}
        memory._store["m2"] = {"text": "world"}
        result = memory.get_all()
        assert len(result) == 2

    def test_get_all_returns_list_copy(self, memory):
        memory._store["m1"] = {"text": "hello"}
        result1 = memory.get_all()
        memory._store["m2"] = {"text": "world"}
        result2 = memory.get_all()
        assert len(result2) == len(result1) + 1

    # -- update --

    def test_update_existing_memory(self, memory):
        memory._store["m1"] = {"text": "old"}
        result = memory.update("m1", {"text": "new"})
        assert result == {"status": "ok"}
        assert memory.get("m1") == {"text": "new"}

    def test_update_nonexistent_memory(self, memory):
        result = memory.update("nonexistent", {"text": "new"})
        assert result == {"status": "not_found"}

    def test_update_empty_data(self, memory):
        memory._store["m1"] = {"text": "old"}
        memory.update("m1", {})
        assert memory.get("m1") == {}

    def test_update_with_none_data(self, memory):
        memory._store["m1"] = {"text": "old"}
        memory.update("m1", None)
        assert memory.get("m1") is None

    # -- delete --

    def test_delete_existing_memory(self, memory):
        memory._store["m1"] = {"text": "hello"}
        result = memory.delete("m1")
        assert result == {"status": "ok"}
        assert memory.get("m1") is None

    def test_delete_nonexistent_memory(self, memory):
        result = memory.delete("nonexistent")
        assert result == {"status": "not_found"}

    def test_delete_removes_from_store(self, memory):
        memory._store["m1"] = {"text": "hello"}
        memory._store["m2"] = {"text": "world"}
        memory.delete("m1")
        assert len(memory.get_all()) == 1
        assert memory.get("m2") is not None

    # -- history --

    def test_history_empty(self, memory):
        result = memory.history("m1")
        assert result == []

    def test_history_existing(self, memory):
        memory._history["m1"] = [
            {"old": "v1", "new": "v2"},
            {"old": "v2", "new": "v3"},
        ]
        result = memory.history("m1")
        assert len(result) == 2

    def test_history_nonexistent_memory(self, memory):
        result = memory.history("nonexistent")
        assert result == []

    def test_history_returns_copy(self, memory):
        memory._history["m1"] = [{"old": "v1", "new": "v2"}]
        result1 = memory.history("m1")
        result1.append({"old": "v3", "new": "v4"})
        assert len(memory.history("m1")) == 1
