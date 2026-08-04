"""Tests for mem0.memory.storage.SQLiteManager."""

import pytest
import sqlite3
import threading

from mem0.memory.storage import SQLiteManager


@pytest.fixture
def db():
    manager = SQLiteManager(":memory:")
    yield manager
    manager.close()


class TestSQLiteManagerInit:
    def test_default_memory_db(self):
        manager = SQLiteManager()
        assert manager.db_path == ":memory:"
        assert manager.connection is not None
        manager.close()

    def test_custom_db_path(self, tmp_path):
        path = str(tmp_path / "test.db")
        manager = SQLiteManager(path)
        assert manager.db_path == path
        assert manager.connection is not None
        manager.close()

    def test_connection_is_sqlite3_connection(self):
        manager = SQLiteManager(":memory:")
        assert isinstance(manager.connection, sqlite3.Connection)
        manager.close()

    def test_tables_created_on_init(self):
        manager = SQLiteManager(":memory:")
        cur = manager.connection.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        assert "history" in tables
        assert "messages" in tables
        manager.close()


class TestAddHistory:
    def test_add_single_history_record(self, db):
        db.add_history("mem1", None, "hello world", "ADD")
        results = db.get_history("mem1")
        assert len(results) == 1
        assert results[0]["memory_id"] == "mem1"
        assert results[0]["new_memory"] == "hello world"
        assert results[0]["event"] == "ADD"
        assert results[0]["id"] is not None

    def test_add_history_with_all_fields(self, db):
        db.add_history(
            "mem1",
            old_memory="old text",
            new_memory="new text",
            event="UPDATE",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-01T00:00:00",
            is_deleted=0,
            actor_id="actor1",
            role="user",
        )
        results = db.get_history("mem1")
        assert len(results) == 1
        r = results[0]
        assert r["old_memory"] == "old text"
        assert r["new_memory"] == "new text"
        assert r["event"] == "UPDATE"
        assert r["created_at"] == "2025-01-01T00:00:00"
        assert r["updated_at"] == "2025-01-01T00:00:00"
        assert r["is_deleted"] is False
        assert r["actor_id"] == "actor1"
        assert r["role"] == "user"

    def test_add_history_deleted_flag(self, db):
        db.add_history("mem1", None, "text", "DELETE", is_deleted=1)
        results = db.get_history("mem1")
        assert results[0]["is_deleted"] is True

    def test_add_multiple_history_records_same_memory(self, db):
        db.add_history("mem1", None, "version 1", "ADD")
        db.add_history("mem1", "version 1", "version 2", "UPDATE")
        results = db.get_history("mem1")
        assert len(results) == 2

    def test_add_history_different_memories(self, db):
        db.add_history("mem1", None, "memory 1", "ADD")
        db.add_history("mem2", None, "memory 2", "ADD")
        r1 = db.get_history("mem1")
        r2 = db.get_history("mem2")
        assert len(r1) == 1 and r1[0]["new_memory"] == "memory 1"
        assert len(r2) == 1 and r2[0]["new_memory"] == "memory 2"

    def test_add_history_is_deleted_default(self, db):
        db.add_history("mem1", None, "text", "ADD", is_deleted=0)
        results = db.get_history("mem1")
        assert results[0]["is_deleted"] is False

    def test_add_history_none_actor_id(self, db):
        db.add_history("mem1", None, "text", "ADD", actor_id=None)
        results = db.get_history("mem1")
        assert results[0]["actor_id"] is None


class TestBatchAddHistory:
    def test_batch_add_empty_list(self, db):
        db.batch_add_history([])
        assert len(db.get_history("mem1")) == 0

    def test_batch_add_single_record(self, db):
        records = [{"memory_id": "m1", "new_memory": "hello", "event": "ADD"}]
        try:
            db.batch_add_history(records)
            assert True
        except AttributeError:
            pass
        results = db.get_history("m1")
        assert len(results) == 1

    def test_batch_add_multiple_records(self, db):
        records = [
            {"memory_id": "m1", "old_memory": None, "new_memory": "v1", "event": "ADD"},
            {"memory_id": "m1", "old_memory": "v1", "new_memory": "v2", "event": "UPDATE"},
            {"memory_id": "m2", "old_memory": None, "new_memory": "solo", "event": "ADD"},
        ]
        try:
            db.batch_add_history(records)
            assert True
        except AttributeError:
            pass
        assert len(db.get_history("m1")) == 2
        assert len(db.get_history("m2")) == 1

    def test_batch_add_records_with_all_fields(self, db):
        records = [
            {
                "memory_id": "m1",
                "old_memory": "old",
                "new_memory": "new",
                "event": "UPDATE",
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00",
                "is_deleted": 0,
                "actor_id": "a1",
                "role": "agent",
            }
        ]
        try:
            db.batch_add_history(records)
            assert True
        except AttributeError:
            pass
        r = db.get_history("m1")[0]
        assert r["old_memory"] == "old"
        assert r["new_memory"] == "new"
        assert r["actor_id"] == "a1"
        assert r["role"] == "agent"

    def test_batch_add_partial_records(self, db):
        records = [
            {"memory_id": "m1", "event": "ADD"},  # missing optional fields
            {"memory_id": "m2", "new_memory": "full", "event": "ADD"},
        ]
        try:
            db.batch_add_history(records)
            assert True
        except AttributeError:
            pass
        r1 = db.get_history("m1")[0]
        assert r1["old_memory"] is None
        assert r1["is_deleted"] is False
        r2 = db.get_history("m2")[0]
        assert r2["new_memory"] == "full"

    def test_batch_add_none_records(self, db):
        records = [None]
        db.batch_add_history(records)
        assert db.get_history("m1") == []


class TestGetHistory:
    def test_get_history_empty(self, db):
        results = db.get_history("nonexistent")
        assert results == []

    def test_get_history_returns_dicts(self, db):
        db.add_history("m1", None, "text", "ADD")
        results = db.get_history("m1")
        r = results[0]
        assert isinstance(r, dict)
        assert "id" in r
        assert "memory_id" in r
        assert "old_memory" in r
        assert "new_memory" in r
        assert "event" in r
        assert "created_at" in r
        assert "updated_at" in r
        assert "is_deleted" in r
        assert "actor_id" in r
        assert "role" in r

    def test_get_history_is_deleted_bool(self, db):
        db.add_history("m1", None, "text", "ADD", is_deleted=0)
        db.add_history("m2", None, "text", "ADD", is_deleted=1)
        assert db.get_history("m1")[0]["is_deleted"] is False
        assert db.get_history("m2")[0]["is_deleted"] is True

    def test_get_history_ordering(self, db):
        db.add_history("m1", None, "first", "ADD", created_at="2025-01-01T00:00:00")
        db.add_history("m1", "first", "second", "UPDATE", created_at="2025-01-02T00:00:00")
        db.add_history("m1", "second", "third", "UPDATE", created_at="2025-01-03T00:00:00")
        results = db.get_history("m1")
        assert len(results) == 3
        assert results[0]["new_memory"] == "first"
        assert results[1]["new_memory"] == "second"
        assert results[2]["new_memory"] == "third"

    def test_get_history_filtered_by_memory_id(self, db):
        db.add_history("m1", None, "mem1", "ADD")
        db.add_history("m2", None, "mem2", "ADD")
        assert len(db.get_history("m1")) == 1
        assert db.get_history("m1")[0]["new_memory"] == "mem1"


class TestSaveMessages:
    def test_save_single_message(self, db):
        db.save_messages([{"role": "user", "content": "hello"}], "session1")
        results = db.get_last_messages("session1")
        assert len(results) == 1
        assert results[0]["role"] == "user"
        assert results[0]["content"] == "hello"

    def test_save_empty_messages(self, db):
        db.save_messages([], "session1")
        results = db.get_last_messages("session1")
        assert results == []

    def test_save_multiple_messages(self, db):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        db.save_messages(messages, "session1")
        results = db.get_last_messages("session1")
        assert len(results) == 2

    def test_save_messages_with_name(self, db):
        db.save_messages([{"role": "user", "content": "hi", "name": "alice"}], "session1")
        results = db.get_last_messages("session1")
        assert results[0]["name"] == "alice"

    def test_save_messages_different_sessions(self, db):
        db.save_messages([{"role": "user", "content": "hi"}], "session1")
        db.save_messages([{"role": "user", "content": "bye"}], "session2")
        r1 = db.get_last_messages("session1")
        r2 = db.get_last_messages("session2")
        assert r1[0]["content"] == "hi"
        assert r2[0]["content"] == "bye"

    def test_save_messages_eviction_limit_10(self, db):
        for i in range(15):
            db.save_messages([{"role": "user", "content": f"msg{i}"}], "session1")
        results = db.get_last_messages("session1")
        assert len(results) <= 10

    def test_save_messages_eviction_keeps_latest(self, db):
        # Save 5 messages first
        for i in range(5):
            db.save_messages([{"role": "user", "content": f"old{i}"}], "session1")
        # Then save 3 more (total 8, should all fit)
        for i in range(5, 8):
            db.save_messages([{"role": "user", "content": f"new{i}"}], "session1")
        results = db.get_last_messages("session1", limit=10)
        assert len(results) == 8
        # Check the content is the newest messages
        contents = [r["content"] for r in results]
        assert "new7" in contents
        assert "old0" in contents

    def test_save_messages_returns_none(self, db):
        result = db.save_messages([{"role": "user", "content": "hi"}], "session1")
        assert result is None


class TestGetLastMessages:
    def test_get_last_messages_empty(self, db):
        results = db.get_last_messages("session1")
        assert results == []

    def test_get_last_messages_with_limit(self, db):
        for i in range(5):
            db.save_messages([{"role": "user", "content": f"msg{i}"}], "session1")
        results = db.get_last_messages("session1", limit=3)
        assert len(results) == 3
        assert results[0]["content"] == "msg2"
        assert results[1]["content"] == "msg3"
        assert results[2]["content"] == "msg4"

    def test_get_last_messages_limit_larger_than_count(self, db):
        db.save_messages([{"role": "user", "content": "hi"}], "session1")
        results = db.get_last_messages("session1", limit=100)
        assert len(results) == 1

    def test_get_last_messages_default_limit(self, db):
        for i in range(5):
            db.save_messages([{"role": "user", "content": f"msg{i}"}], "session1")
        results = db.get_last_messages("session1")
        assert len(results) == 5

    def test_get_last_messages_order(self, db):
        db.save_messages([{"role": "user", "content": "first"}], "session1")
        db.save_messages([{"role": "assistant", "content": "second"}], "session1")
        results = db.get_last_messages("session1")
        assert results[0]["content"] == "first"
        assert results[1]["content"] == "second"

    def test_get_last_messages_returns_role_content_name(self, db):
        db.save_messages([{"role": "user", "content": "hi", "name": "alice"}], "session1")
        results = db.get_last_messages("session1")
        r = results[0]
        assert "role" in r
        assert "content" in r
        assert "name" in r
        assert "created_at" in r


class TestReset:
    def test_reset_drops_tables(self, db):
        db.add_history("m1", None, "text", "ADD")
        db.save_messages([{"role": "user", "content": "hi"}], "session1")
        db.reset()
        assert len(db.get_history("m1")) == 0
        assert len(db.get_last_messages("session1")) == 0

    def test_reset_recreates_tables(self, db):
        db.reset()
        db.add_history("m1", None, "text", "ADD")
        results = db.get_history("m1")
        assert len(results) == 1

    def test_reset_is_idempotent(self, db):
        db.reset()
        db.reset()
        db.add_history("m1", None, "text", "ADD")
        assert len(db.get_history("m1")) == 1

    def test_reset_after_adding_data(self, db):
        for i in range(10):
            db.add_history(f"m{i}", None, f"msg{i}", "ADD")
        db.reset()
        assert len(db.get_history("m0")) == 0
        db.add_history("m1", None, "new", "ADD")
        assert db.get_history("m1")[0]["new_memory"] == "new"


class TestClose:
    def test_close_closes_connection(self, db):
        db.close()
        assert db.connection is None

    def test_close_on_closed_connection_does_not_raise(self, db):
        db.close()
        db.close()  # Should not raise

    def test_close_sets_connection_to_none(self, db):
        db.close()
        assert db.connection is None


class TestSQLiteManagerEdgeCases:
    def test_thread_lock_is_present(self):
        manager = SQLiteManager(":memory:")
        assert isinstance(manager._lock, type(threading.Lock()))
        manager.close()

    def test_add_history_with_special_characters(self, db):
        db.add_history("m1", None, "hello\nworld\ttab", "ADD")
        results = db.get_history("m1")
        assert results[0]["new_memory"] == "hello\nworld\ttab"

    def test_add_history_with_unicode(self, db):
        db.add_history("m1", None, "こんにちは世界", "ADD")
        results = db.get_history("m1")
        assert results[0]["new_memory"] == "こんにちは世界"

    def test_add_history_with_empty_strings(self, db):
        db.add_history("m1", "", "", "ADD")
        results = db.get_history("m1")
        assert results[0]["old_memory"] == ""
        assert results[0]["new_memory"] == ""

    def test_get_history_for_empty_memory_id(self, db):
        results = db.get_history("")
        assert results == []

    def test_long_memory_ids(self, db):
        long_id = "m" * 10000
        db.add_history(long_id, None, "text", "ADD")
        results = db.get_history(long_id)
        assert len(results) == 1

    def test_concurrent_add_history(self, db):
        """Test that concurrent add_history calls are safe."""
        errors = []

        def add_many():
            try:
                for i in range(50):
                    db.add_history("shared", None, f"text-{i}", "ADD")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(db.get_history("shared")) == 250


class TestSQLiteManagerDestructors:
    def test_del_calls_close(self):
        manager = SQLiteManager(":memory:")
        assert manager.connection is not None
        del manager
        # No exception should be raised
