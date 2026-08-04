"""Tests for mem0.client.types — Pydantic option models."""

import pytest

from mem0.client.types import (
    AddMemoryOptions,
    DeleteAllMemoryOptions,
    GetAllMemoryOptions,
    ProjectUpdateOptions,
    SearchMemoryOptions,
    UpdateMemoryOptions,
)


class TestAddMemoryOptions:
    def test_default_values(self):
        opts = AddMemoryOptions()
        assert opts.filters is None
        assert opts.metadata is None
        assert opts.infer is None
        assert opts.custom_categories is None
        assert opts.custom_instructions is None
        assert opts.timestamp is None
        assert opts.structured_data_schema is None

    def test_with_all_fields(self):
        opts = AddMemoryOptions(
            filters={"user_id": "u1"},
            metadata={"key": "val"},
            infer=True,
            custom_categories=[{"name": "fact"}],
            custom_instructions="extract facts",
            timestamp=1234567890,
            structured_data_schema={"type": "object"},
        )
        assert opts.filters == {"user_id": "u1"}
        assert opts.infer is True
        assert opts.timestamp == 1234567890

    def test_model_dump_excludes_unset(self):
        opts = AddMemoryOptions(infer=True)
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"infer": True}
        assert "filters" not in dumped

    def test_model_dump_includes_set(self):
        opts = AddMemoryOptions(infer=False)
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"infer": False}


class TestSearchMemoryOptions:
    def test_default_values(self):
        opts = SearchMemoryOptions()
        assert opts.filters is None
        assert opts.top_k is None
        assert opts.rerank is None
        assert opts.threshold is None
        assert opts.fields is None
        assert opts.categories is None

    def test_with_fields(self):
        opts = SearchMemoryOptions(fields=["memory", "id"], categories=["fact"])
        assert opts.fields == ["memory", "id"]
        assert opts.categories == ["fact"]

    def test_with_threshold(self):
        opts = SearchMemoryOptions(threshold=0.7)
        assert opts.threshold == 0.7

    def test_model_dump_excludes_unset(self):
        opts = SearchMemoryOptions(top_k=5)
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"top_k": 5}


class TestGetAllMemoryOptions:
    def test_default_values(self):
        opts = GetAllMemoryOptions()
        assert opts.filters is None
        assert opts.page is None
        assert opts.page_size is None
        assert opts.start_date is None
        assert opts.end_date is None
        assert opts.categories is None

    def test_with_pagination(self):
        opts = GetAllMemoryOptions(page=1, page_size=20)
        assert opts.page == 1
        assert opts.page_size == 20

    def test_with_date_range(self):
        opts = GetAllMemoryOptions(
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-12-31T23:59:59Z",
        )
        assert "2024-01-01" in opts.start_date
        assert "2024-12-31" in opts.end_date

    def test_model_dump_excludes_unset(self):
        opts = GetAllMemoryOptions(page=2)
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"page": 2}


class TestDeleteAllMemoryOptions:
    def test_default_values(self):
        opts = DeleteAllMemoryOptions()
        assert opts.filters is None

    def test_with_filters(self):
        opts = DeleteAllMemoryOptions(filters={"user_id": "u1"})
        assert opts.filters == {"user_id": "u1"}

    def test_model_dump(self):
        opts = DeleteAllMemoryOptions(filters={"agent_id": "a1"})
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"filters": {"agent_id": "a1"}}


class TestUpdateMemoryOptions:
    def test_default_values(self):
        opts = UpdateMemoryOptions()
        assert opts.text is None
        assert opts.metadata is None
        assert opts.timestamp is None

    def test_with_text(self):
        opts = UpdateMemoryOptions(text="new content")
        assert opts.text == "new content"

    def test_with_metadata(self):
        opts = UpdateMemoryOptions(metadata={"key": "val", "nested": {"a": 1}})
        assert opts.metadata["key"] == "val"

    def test_with_int_timestamp(self):
        opts = UpdateMemoryOptions(timestamp=1234567890)
        assert opts.timestamp == 1234567890

    def test_with_float_timestamp(self):
        opts = UpdateMemoryOptions(timestamp=1234567890.123)
        assert opts.timestamp == 1234567890.123

    def test_with_string_timestamp(self):
        opts = UpdateMemoryOptions(timestamp="2024-01-01T00:00:00Z")
        assert opts.timestamp == "2024-01-01T00:00:00Z"

    def test_model_dump_excludes_unset(self):
        opts = UpdateMemoryOptions(text="updated")
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"text": "updated"}


class TestProjectUpdateOptions:
    def test_default_values(self):
        opts = ProjectUpdateOptions()
        assert opts.custom_instructions is None
        assert opts.custom_categories is None
        assert opts.memory_depth is None
        assert opts.usecase_setting is None
        assert opts.multilingual is None
        assert opts.retrieval_criteria is None

    def test_with_custom_instructions(self):
        opts = ProjectUpdateOptions(custom_instructions="new instructions")
        assert opts.custom_instructions == "new instructions"

    def test_with_custom_categories(self):
        opts = ProjectUpdateOptions(custom_categories=[{"name": "fact"}, {"name": "preference"}])
        assert len(opts.custom_categories) == 2

    def test_with_multilingual(self):
        opts = ProjectUpdateOptions(multilingual=True)
        assert opts.multilingual is True

    def test_with_memory_depth(self):
        opts = ProjectUpdateOptions(memory_depth="extended")
        assert opts.memory_depth == "extended"

    def test_model_dump_excludes_unset(self):
        opts = ProjectUpdateOptions(multilingual=False)
        dumped = opts.model_dump(exclude_unset=True)
        assert dumped == {"multilingual": False}

    def test_all_fields_set(self):
        opts = ProjectUpdateOptions(
            custom_instructions="do X",
            custom_categories=[{"name": "A"}],
            memory_depth="extended",
            multilingual=True,
            retrieval_criteria=[{"field": "score"}],
        )
        dumped = opts.model_dump(exclude_unset=True)
        assert "custom_instructions" in dumped
        assert "custom_categories" in dumped
        assert "memory_depth" in dumped
        assert "multilingual" in dumped
        assert "retrieval_criteria" in dumped
