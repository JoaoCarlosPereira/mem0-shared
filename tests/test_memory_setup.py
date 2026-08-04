"""Tests for mem0.memory.setup functions."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mem0_dir(tmp_path):
    """Provide a temporary mem0 directory."""
    return str(tmp_path / ".mem0")


@pytest.fixture
def config_path(mem0_dir):
    """Provide the path to config.json."""
    return os.path.join(mem0_dir, "config.json")


@pytest.fixture(autouse=True)
def _patch_mem0_dir(monkeypatch, mem0_dir):
    """Use temporary directory for all config operations."""
    monkeypatch.setattr("mem0.memory.setup.mem0_dir", mem0_dir)


@pytest.fixture
def _reload_setup_module(monkeypatch, mem0_dir):
    """Reload the setup module to pick up the new mem0_dir."""
    import importlib
    import mem0.memory.setup as setup_mod
    monkeypatch.setattr(setup_mod, "mem0_dir", mem0_dir)
    monkeypatch.setattr(setup_mod, "mem0_dir", mem0_dir)
    importlib.reload(setup_mod)
    return setup_mod


class TestConfigPath:
    def test_config_path_in_mem0_dir(self, config_path):
        import mem0.memory.setup as setup_mod
        assert setup_mod._config_path() == config_path

    def test_config_path_filename(self, config_path):
        import mem0.memory.setup as setup_mod
        assert setup_mod._config_path().endswith("config.json")


class TestLoadConfig:
    def test_missing_config_file(self):
        import mem0.memory.setup as setup_mod
        assert setup_mod._load_config() == {}

    def test_empty_config_file(self, config_path, mem0_dir):
        os.makedirs(mem0_dir, exist_ok=True)
        with open(config_path, "w") as f:
            f.write("{}")
        import mem0.memory.setup as setup_mod
        assert setup_mod._load_config() == {}

    def test_valid_config(self, config_path, mem0_dir):
        os.makedirs(mem0_dir, exist_ok=True)
        data = {"user_id": "abc123", "telemetry": {"anonymous_id": "xyz"}}
        with open(config_path, "w") as f:
            json.dump(data, f)
        import mem0.memory.setup as setup_mod
        result = setup_mod._load_config()
        assert result == data

    def test_invalid_json_returns_empty(self, config_path, mem0_dir):
        os.makedirs(mem0_dir, exist_ok=True)
        with open(config_path, "w") as f:
            f.write("not json {{{")
        import mem0.memory.setup as setup_mod
        assert setup_mod._load_config() == {}

    def test_json_array_returns_empty(self, config_path, mem0_dir):
        os.makedirs(mem0_dir, exist_ok=True)
        with open(config_path, "w") as f:
            f.write("[1, 2, 3]")
        import mem0.memory.setup as setup_mod
        assert setup_mod._load_config() == {}

    def test_config_with_nested_dict(self, config_path, mem0_dir):
        os.makedirs(mem0_dir, exist_ok=True)
        data = {"telemetry": {"anonymous_id": "abc", "aliased_pairs": []}}
        with open(config_path, "w") as f:
            json.dump(data, f)
        import mem0.memory.setup as setup_mod
        result = setup_mod._load_config()
        assert result["telemetry"]["anonymous_id"] == "abc"


class TestWriteConfig:
    def test_write_config_creates_file(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"user_id": "new"})
        assert os.path.exists(config_path)

    def test_write_config_writes_valid_json(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"key": "value", "nested": {"a": 1}})
        with open(config_path) as f:
            data = json.load(f)
        assert data == {"key": "value", "nested": {"a": 1}}

    def test_write_config_idempotent(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"user_id": "u1"})
        setup_mod._write_config({"user_id": "u2"})
        with open(config_path) as f:
            data = json.load(f)
        assert data == {"user_id": "u2"}

    def test_write_config_creates_parent_dir(self, mem0_dir):
        import mem0.memory.setup as setup_mod
        fake_dir = os.path.join(mem0_dir, "sub", "deep")
        with patch.object(setup_mod, "mem0_dir", fake_dir):
            with patch.object(setup_mod, "_config_path", lambda: os.path.join(fake_dir, "config.json")):
                setup_mod._write_config({"key": "val"})
                assert os.path.exists(os.path.join(fake_dir, "config.json"))


class TestSetupConfig:
    def test_setup_config_creates_user_id(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod.setup_config()
        with open(config_path) as f:
            data = json.load(f)
        assert "user_id" in data
        assert data["user_id"] is not None

    def test_setup_config_noop_when_user_id_exists(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"user_id": "existing_id"})
        setup_mod.setup_config()
        with open(config_path) as f:
            data = json.load(f)
        assert data["user_id"] == "existing_id"

    def test_setup_config_adds_user_id_to_existing(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"telemetry": {"anonymous_id": "abc"}})
        setup_mod.setup_config()
        with open(config_path) as f:
            data = json.load(f)
        assert data["user_id"] is not None
        assert data["telemetry"]["anonymous_id"] == "abc"

    def test_setup_config_returns_none(self, config_path):
        import mem0.memory.setup as setup_mod
        assert setup_mod.setup_config() is None


class TestGetUserId:
    def test_get_user_id_existing(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"user_id": "test_user"})
        assert setup_mod.get_user_id() == "test_user"

    def test_get_user_id_missing_returns_anonymous(self, config_path):
        import mem0.memory.setup as setup_mod
        assert setup_mod.get_user_id() == "anonymous_user"

    def test_get_user_id_empty_config(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({})
        assert setup_mod.get_user_id() == "anonymous_user"


class TestReadAnonIds:
    def test_read_anon_ids_empty_config(self):
        import mem0.memory.setup as setup_mod
        result = setup_mod.read_anon_ids()
        assert result["oss"] is None
        assert result["cli"] is None
        assert result["aliased_pairs"] == []

    def test_read_anon_ids_with_oss_user_id(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"user_id": "oss_123"})
        result = setup_mod.read_anon_ids()
        assert result["oss"] == "oss_123"
        assert result["cli"] is None

    def test_read_anon_ids_with_cli_anonymous_id(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"telemetry": {"anonymous_id": "cli_456"}})
        result = setup_mod.read_anon_ids()
        assert result["cli"] == "cli_456"

    def test_read_anon_ids_with_both(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({
            "user_id": "oss_123",
            "telemetry": {"anonymous_id": "cli_456"}
        })
        result = setup_mod.read_anon_ids()
        assert result["oss"] == "oss_123"
        assert result["cli"] == "cli_456"

    def test_read_anon_ids_with_aliased_pairs(self, config_path):
        import mem0.memory.setup as setup_mod
        pairs = ["marker1", "marker2"]
        setup_mod._write_config({
            "user_id": "oss_123",
            "telemetry": {"anonymous_id": "cli_456", "aliased_pairs": pairs}
        })
        result = setup_mod.read_anon_ids()
        assert result["aliased_pairs"] == pairs

    def test_read_anon_ids_invalid_aliased_pairs_returns_empty(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({
            "telemetry": {"aliased_pairs": "not a list"}
        })
        result = setup_mod.read_anon_ids()
        assert result["aliased_pairs"] == []


class TestAliasPairMarker:
    def test_alias_pair_marker_returns_string(self):
        import mem0.memory.setup as setup_mod
        result = setup_mod._alias_pair_marker("anon1", "user@example.com")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_alias_pair_marker_deterministic(self):
        import mem0.memory.setup as setup_mod
        r1 = setup_mod._alias_pair_marker("anon1", "user@example.com")
        r2 = setup_mod._alias_pair_marker("anon1", "user@example.com")
        assert r1 == r2

    def test_alias_pair_marker_different_input_different_output(self):
        import mem0.memory.setup as setup_mod
        r1 = setup_mod._alias_pair_marker("anon1", "user1@example.com")
        r2 = setup_mod._alias_pair_marker("anon2", "user2@example.com")
        assert r1 != r2


class TestIsAliased:
    def test_is_aliased_empty_anon_id(self):
        import mem0.memory.setup as setup_mod
        assert setup_mod.is_aliased("", "user@example.com") is False

    def test_is_aliased_empty_email(self):
        import mem0.memory.setup as setup_mod
        assert setup_mod.is_aliased("anon1", "") is False

    def test_is_aliased_not_in_pairs(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"telemetry": {"aliased_pairs": ["other_marker"]}})
        assert setup_mod.is_aliased("anon1", "user@example.com") is False

    def test_is_aliased_in_pairs(self, config_path):
        import mem0.memory.setup as setup_mod
        marker = setup_mod._alias_pair_marker("anon1", "user@example.com")
        setup_mod._write_config({"telemetry": {"aliased_pairs": [marker]}})
        assert setup_mod.is_aliased("anon1", "user@example.com") is True

    def test_is_aliased_no_telemetry_key(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({})
        assert setup_mod.is_aliased("anon1", "user@example.com") is False

    def test_is_aliased_telemetry_not_dict(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"telemetry": "string"})
        assert setup_mod.is_aliased("anon1", "user@example.com") is False

    def test_is_aliased_aliased_pairs_not_list(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"telemetry": {"aliased_pairs": "not list"}})
        assert setup_mod.is_aliased("anon1", "user@example.com") is False


class TestMarkAliased:
    def test_mark_aliased_empty_anon_id(self):
        import mem0.memory.setup as setup_mod
        setup_mod.mark_aliased("", "user@example.com")
        # Should not raise

    def test_mark_aliased_empty_email(self):
        import mem0.memory.setup as setup_mod
        setup_mod.mark_aliased("anon1", "")
        # Should not raise

    def test_mark_aliased_adds_marker(self, config_path):
        import mem0.memory.setup as setup_mod
        marker = setup_mod._alias_pair_marker("anon1", "user@example.com")
        setup_mod.mark_aliased("anon1", "user@example.com")
        result = setup_mod.read_anon_ids()
        assert marker in result["aliased_pairs"]

    def test_mark_aliased_not_duplicate(self, config_path):
        import mem0.memory.setup as setup_mod
        marker = setup_mod._alias_pair_marker("anon1", "user@example.com")
        setup_mod.mark_aliased("anon1", "user@example.com")
        setup_mod.mark_aliased("anon1", "user@example.com")
        result = setup_mod.read_anon_ids()
        assert result["aliased_pairs"].count(marker) == 1

    def test_mark_aliased_creates_telemetry_key(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod.mark_aliased("anon1", "user@example.com")
        with open(config_path) as f:
            data = json.load(f)
        assert "telemetry" in data
        assert "aliased_pairs" in data["telemetry"]


class TestGetOrCreateUserId:
    def test_returns_user_id_without_vector_store(self):
        import mem0.memory.setup as setup_mod
        result = setup_mod.get_or_create_user_id(vector_store=None)
        assert result == "anonymous_user"

    def test_returns_user_id_from_config(self, config_path):
        import mem0.memory.setup as setup_mod
        setup_mod._write_config({"user_id": "config_user"})
        result = setup_mod.get_or_create_user_id(vector_store=None)
        assert result == "config_user"

    def test_with_vector_store_no_existing(self):
        import mem0.memory.setup as setup_mod
        mock_vs = MagicMock()
        mock_vs.get.side_effect = Exception("Not found")
        result = setup_mod.get_or_create_user_id(mock_vs)
        assert result == "anonymous_user"
        mock_vs.insert.assert_called_once()

    def test_with_vector_store_existing_user_id(self):
        import mem0.memory.setup as setup_mod
        mock_match = MagicMock()
        mock_match.payload = {"user_id": "stored_user"}
        mock_vs = MagicMock()
        mock_vs.get.return_value = mock_match
        result = setup_mod.get_or_create_user_id(mock_vs)
        assert result == "stored_user"
        mock_vs.insert.assert_not_called()

    def test_with_vector_store_none_payload(self):
        import mem0.memory.setup as setup_mod
        mock_vs = MagicMock()
        mock_vs.get.return_value = MagicMock(payload=None)
        result = setup_mod.get_or_create_user_id(mock_vs)
        assert result == "anonymous_user"
        mock_vs.insert.assert_called_once()

    def test_with_vector_store_none_stored_id(self):
        import mem0.memory.setup as setup_mod
        mock_match = MagicMock()
        mock_match.payload = {"user_id": None}
        mock_vs = MagicMock()
        mock_vs.get.return_value = mock_match
        result = setup_mod.get_or_create_user_id(mock_vs)
        assert result == "anonymous_user"
        mock_vs.insert.assert_called_once()

    def test_with_vector_store_no_payload_attr(self):
        import mem0.memory.setup as setup_mod
        mock_match = MagicMock()
        mock_match.payload = None
        mock_vs = MagicMock()
        mock_vs.get.return_value = mock_match
        result = setup_mod.get_or_create_user_id(mock_vs)
        assert result == "anonymous_user"
        mock_vs.insert.assert_called_once()
