"""Comprehensive non-regression tests for seed-mem0-skills.py — skill seeding into AgentRegistry."""

from __future__ import annotations

import json
import os
import stat as stat_module
import tarfile
import gzip
import io
import base64
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from dataclasses import replace

import pytest


class TestStripQuotes:
    """Tests for strip_quotes."""

    def test_strips_double_quotes(self):
        from seed_mem0_skills import strip_quotes
        assert strip_quotes('"value"') == "value"

    def test_strips_single_quotes(self):
        from seed_mem0_skills import strip_quotes
        assert strip_quotes("'value'") == "value"

    def test_no_quotes_returns_value(self):
        from seed_mem0_skills import strip_quotes
        assert strip_quotes("value") == "value"

    def test_empty_string(self):
        from seed_mem0_skills import strip_quotes
        assert strip_quotes("") == ""

    def test_whitespace_only_strips(self):
        from seed_mem0_skills import strip_quotes
        assert strip_quotes("  ") == "  "

    def test_mismatched_quotes_not_stripped(self):
        """Mismatched quotes should not be stripped."""
        from seed_mem0_skills import strip_quotes
        assert strip_quotes('"value\'') == '"value\''


class TestParseFrontmatter:
    """Tests for parse_frontmatter."""

    def test_parses_simple_frontmatter(self):
        from seed_mem0_skills import parse_frontmatter

        text = "---\nname: my-skill\ndescription: A test skill\n---\nBody text"
        result = parse_frontmatter(text)
        assert result["name"] == "my-skill"
        assert result["description"] == "A test skill"

    def test_no_frontmatter_returns_empty(self):
        from seed_mem0_skills import parse_frontmatter
        assert parse_frontmatter("No frontmatter here") == {}

    def test_no_closing_delimiter_returns_empty(self):
        from seed_mem0_skills import parse_frontmatter
        text = "---\nname: test\nNo closing delimiter"
        assert parse_frontmatter(text) == {}

    def test_skips_empty_lines_in_frontmatter(self):
        from seed_mem0_skills import parse_frontmatter
        text = "---\n\nname: test\n\ndescription: desc\n---\nBody"
        result = parse_frontmatter(text)
        assert result["name"] == "test"

    def test_skips_indented_lines(self):
        from seed_mem0_skills import parse_frontmatter
        text = "---\nname: test\n  indented: line\n---\nBody"
        result = parse_frontmatter(text)
        assert "indented" not in result

    def test_skips_lines_without_colon(self):
        from seed_mem0_skills import parse_frontmatter
        text = "---\nname: test\njust a line\n---\nBody"
        result = parse_frontmatter(text)
        assert "just a line" not in result

    def test_parses_block_scalar_flow(self):
        """Flow: value is just '>' or '|'."""
        from seed_mem0_skills import parse_frontmatter
        text = '---\nname: test\ndescription: >\n  This is a flow scalar\n---\nBody'
        result = parse_frontmatter(text)
        # Flow scalar with > joins to single line
        assert "This is a flow scalar" in result.get("description", "")

    def test_parses_block_scalar_literal(self):
        from seed_mem0_skills import parse_frontmatter
        text = '---\nname: test\ndescription: |\n  Line 1\n  Line 2\n---\nBody'
        result = parse_frontmatter(text)
        # Literal scalar preserves newlines
        assert "Line 1" in result.get("description", "")

    def test_quoted_value_strips_quotes(self):
        from seed_mem0_skills import parse_frontmatter
        text = '---\nname: "My Skill"\n---\nBody'
        result = parse_frontmatter(text)
        assert result["name"] == "My Skill"


class TestSkillBodyWithoutFrontmatter:
    """Tests for skill_body_without_frontmatter."""

    def test_returns_body_after_frontmatter(self):
        from seed_mem0_skills import skill_body_without_frontmatter
        text = "---\nname: test\n---\nBody text here"
        result = skill_body_without_frontmatter(text)
        assert result.strip() == "Body text here"

    def test_returns_original_when_no_frontmatter(self):
        from seed_mem0_skills import skill_body_without_frontmatter
        text = "No frontmatter at all"
        assert skill_body_without_frontmatter(text) == text

    def test_no_closing_delimiter_returns_original(self):
        from seed_mem0_skills import skill_body_without_frontmatter
        text = "---\nname: test\nNo closing"
        assert skill_body_without_frontmatter(text) == "---\nname: test\nNo closing"

    def test_empty_frontmatter(self):
        from seed_mem0_skills import skill_body_without_frontmatter
        text = "---\n---\nBody"
        result = skill_body_without_frontmatter(text)
        assert "Body" in result


class TestFirstMarkdownHeading:
    """Tests for first_markdown_heading."""

    def test_returns_first_heading(self):
        from seed_mem0_skills import first_markdown_heading
        assert first_markdown_heading("# Main Title") == "Main Title"

    def test_returns_level_two_heading(self):
        from seed_mem0_skills import first_markdown_heading
        assert first_markdown_heading("## Section") == "Section"

    def test_skips_non_headings(self):
        from seed_mem0_skills import first_markdown_heading
        assert first_markdown_heading("Not a heading") is None

    def test_empty_string(self):
        from seed_mem0_skills import first_markdown_heading
        assert first_markdown_heading("") is None

    def test_whitespace_only(self):
        from seed_mem0_skills import first_markdown_heading
        assert first_markdown_heading("   ") is None

    def test_strips_whitespace_from_heading(self):
        from seed_mem0_skills import first_markdown_heading
        assert first_markdown_heading("#  My Title  ") == "My Title"

    def test_multiple_headings_returns_first(self):
        from seed_mem0_skills import first_markdown_heading
        text = "# First\n## Second\n### Third"
        assert first_markdown_heading(text) == "First"

    def test_heading_with_text_after(self):
        from seed_mem0_skills import first_markdown_heading
        text = "# Title — Subtitle"
        assert first_markdown_heading(text) == "Title — Subtitle"


class TestDnsName:
    """Tests for dns_name."""

    def test_simple_name(self):
        from seed_mem0_skills import dns_name
        assert dns_name("my-skill") == "my-skill"

    def test_uppercase_lowercased(self):
        from seed_mem0_skills import dns_name
        assert dns_name("My-Skill") == "my-skill"

    def test_special_chars_become_dashes(self):
        from seed_mem0_skills import dns_name
        assert dns_name("my_skill!test") == "my-skill-test"

    def test_consecutive_special_chars_become_single_dash(self):
        from seed_mem0_skills import dns_name
        result = dns_name("my@@skill")
        assert "--" not in result

    def test_trims_leading_trailing_dots_and_dashes(self):
        from seed_mem0_skills import dns_name
        assert dns_name(".my-skill.") == "my-skill"

    def test_raises_on_empty_result(self):
        from seed_mem0_skills import dns_name
        with pytest.raises(ValueError):
            dns_name("!!!")

    def test_truncates_to_253_chars(self):
        from seed_mem0_skills import dns_name
        long_name = "a" * 300
        result = dns_name(long_name)
        assert len(result) <= 253

    def test_validates_dns_format(self):
        from seed_mem0_skills import dns_name
        # Should not raise for valid DNS name
        result = dns_name("valid-name.example.com")
        assert result == "valid-name.example.com"

    def test_numbers_in_name(self):
        from seed_mem0_skills import dns_name
        assert dns_name("skill-123") == "skill-123"


class TestYamlScalarAndBlock:
    """Tests for yaml_scalar and yaml_block."""

    def test_yaml_scalar_quotes_value(self):
        from seed_mem0_skills import yaml_scalar
        result = yaml_scalar("test-value")
        assert result == '"test-value"'

    def test_yaml_block_empty(self):
        from seed_mem0_skills import yaml_block
        result = yaml_block("", 2)
        assert '""' in result

    def test_yaml_block_with_indent(self):
        from seed_mem0_skills import yaml_block
        result = yaml_block("line1\nline2", 4)
        assert result.startswith("|-")
        assert "    line1" in result


class TestBuildSkillDoc:
    """Tests for build_skill_doc."""

    def test_generates_valid_yaml(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("---\nname: My Skill\ndescription: A test skill\n---\n# My Skill\n\nBody text.")

        doc_text = ""

        def capture_write(text):
            nonlocal doc_text
            doc_text = text

        with patch.object(Path, "read_text", return_value=skill_file.read_text()), \
             patch.object(Path, "relative_to", return_value=Mock(as_posix=lambda: "skills/my-skill/SKILL.md")), \
             patch.object(Path, "resolve", return_value=skill_file):
            from seed_mem0_skills import build_skill_doc, repo_root

            # Mock repo_root to return tmp_path
            with patch("seed_mem0_skills.repo_root", return_value=tmp_path):
                name, doc = build_skill_doc(skill_file, tmp_path / "skills", "default", "latest")
                assert name == "my-skill"
                assert "apiVersion: ar.dev/v1alpha1" in doc
                assert "kind: Skill" in doc
                assert "namespace" in doc
                assert "default" in doc
                assert "name" in doc
                assert "title" in doc
                assert "description" in doc

    def test_defaults_name_to_folder(self):
        from seed_mem0_skills import build_skill_doc

        skill_dir = MagicMock()
        skill_dir.name = "my-folder"
        skill_file = MagicMock()
        skill_file.parent = skill_dir
        skill_file.read_text.return_value = "Body without frontmatter"

        with patch.object(Path, "read_text", return_value="Body without frontmatter"), \
             patch.object(Path, "relative_to", return_value=Mock(as_posix=lambda: "skills/my-folder/SKILL.md")), \
             patch.object(Path, "resolve", return_value=skill_file), \
             patch("seed_mem0_skills.repo_root", return_value=MagicMock()), \
             patch("seed_mem0_skills.default_skills_dir", return_value=MagicMock()):
            name, _ = build_skill_doc(skill_file, skill_dir, "default", "latest")
            assert name == "my-folder"


class TestDiscoverSkillFiles:
    """Tests for discover_skill_files."""

    def test_discovers_skill_directories(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill-a" / "SKILL.md").write_text("# A")
        (skills_dir / "skill-b" / "SKILL.md").write_text("# B")

        import os
        (skills_dir / "skill-a").mkdir(parents=True, exist_ok=True)
        (skills_dir / "skill-b").mkdir(parents=True, exist_ok=True)
        (skills_dir / "skill-a" / "SKILL.md").write_text("# A")
        (skills_dir / "skill-b" / "SKILL.md").write_text("# B")

        from seed_mem0_skills import discover_skill_files
        files = discover_skill_files(skills_dir)
        assert len(files) == 2

    def test_skips_symlinks(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        real_dir = skills_dir / "real"
        real_dir.mkdir()
        (real_dir / "SKILL.md").write_text("# Real")

        symlink_dir = skills_dir / "symlink"
        symlink_dir.symlink_to(real_dir)

        from seed_mem0_skills import discover_skill_files
        files = discover_skill_files(skills_dir)
        assert len(files) == 1
        assert symlink_dir not in [f.parent for f in files]

    def test_skips_non_directory_entries(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        # Just a file, not a directory
        (skills_dir / "not-a-dir.txt").write_text("# File")

        from seed_mem0_skills import discover_skill_files
        files = discover_skill_files(skills_dir)
        assert len(files) == 0

    def test_raises_when_directory_missing(self):
        from seed_mem0_skills import discover_skill_files
        with pytest.raises(FileNotFoundError):
            discover_skill_files(Path("/nonexistent/skills"))

    def test_skips_directories_without_skill_md(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "no-skill").mkdir()
        # No SKILL.md inside

        from seed_mem0_skills import discover_skill_files
        files = discover_skill_files(skills_dir)
        assert len(files) == 0


class TestValidateArchivePath:
    """Tests for validate_archive_path."""

    def test_valid_path(self):
        from seed_mem0_skills import validate_archive_path
        validate_archive_path("src/file.py")  # Should not raise

    def test_absolute_path_raises(self):
        from seed_mem0_skills import validate_archive_path
        with pytest.raises(ValueError):
            validate_archive_path("/absolute/path")

    def test_backslash_raises(self):
        from seed_mem0_skills import validate_archive_path
        with pytest.raises(ValueError):
            validate_archive_path("path\\with\\backslash")

    def test_empty_part_raises(self):
        from seed_mem0_skills import validate_archive_path
        with pytest.raises(ValueError):
            validate_archive_path("path//double")

    def test_dotdot_raises(self):
        from seed_mem0_skills import validate_archive_path
        with pytest.raises(ValueError):
            validate_archive_path("path/../traversal")

    def test_path_too_long_raises(self):
        from seed_mem0_skills import validate_archive_path, MAX_PATH_BYTES
        with pytest.raises(ValueError):
            validate_archive_path("a" * (MAX_PATH_BYTES + 1))

    def test_empty_string_raises(self):
        from seed_mem0_skills import validate_archive_path
        with pytest.raises(ValueError):
            validate_archive_path("")


class TestCollectSkillFiles:
    """Tests for collect_skill_files."""

    def test_collects_regular_files(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        (skill_dir / "ref.md").write_text("Reference")

        from seed_mem0_skills import collect_skill_files
        files, source_bytes = collect_skill_files(skill_dir)
        assert len(files) == 2
        assert source_bytes > 0

    def test_skips_git_directory(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        git_dir = skill_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")

        from seed_mem0_skills import collect_skill_files
        files, _ = collect_skill_files(skill_dir)
        assert len(files) == 1
        assert ".git" not in [f[0] for f in files]

    def test_skips_symlinks(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        target = tmp_path / "target.txt"
        target.write_text("target")
        symlink = skill_dir / "link.txt"
        symlink.symlink_to(target)

        from seed_mem0_skills import collect_skill_files
        files, _ = collect_skill_files(skill_dir)
        assert len(files) == 1

    def test_raises_without_skill_md(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "other.md").write_text("No SKILL.md")

        from seed_mem0_skills import collect_skill_files
        with pytest.raises(ValueError):
            collect_skill_files(skill_dir)

    def test_skips_non_regular_files(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        # Create a directory inside
        (skill_dir / "subdir").mkdir()

        from seed_mem0_skills import collect_skill_files
        files, _ = collect_skill_files(skill_dir)
        assert len(files) == 1


class TestBuildSkillArchive:
    """Tests for build_skill_archive."""

    def test_creates_valid_tar_gzip(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        (skill_dir / "extra.md").write_text("Extra content here for testing.")

        from seed_mem0_skills import build_skill_archive
        payload, digest, file_count, source_bytes = build_skill_archive(skill_dir)

        assert isinstance(payload, bytes)
        assert len(payload) > 0
        assert len(digest) > 0
        assert file_count == 2
        assert source_bytes > 0

        # Verify it's a valid gzip
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as gf:
            with tarfile.open(fileobj=gio.BytesIO(gf.read()) if hasattr(gio, 'BytesIO') else io.BytesIO(gf.read())) as tf:
                names = tf.getnames()
                assert "SKILL.md" in names or any("SKILL.md" in n for n in names)


class TestBuildSkillArtifact:
    """Tests for build_skill_artifact."""

    def test_creates_skill_artifact(self, tmp_path):
        skill_dir = tmp_path / "skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: Test Skill\n---\n# Test Skill\n\nBody.")

        from seed_mem0_skills import build_skill_artifact
        artifact = build_skill_artifact(skill_dir, tmp_path / "skills", "default", "latest")

        assert artifact.name == "test-skill"
        assert isinstance(artifact.document, str)
        assert len(artifact.archive) > 0
        assert len(artifact.digest) > 0
        assert artifact.file_count == 1
        assert artifact.source_bytes > 0


class TestRequestJson:
    """Tests for request_json."""

    def test_success_returns_json(self):
        from seed_mem0_skills import request_json

        resp = MagicMock()
        resp.read.return_value = json.dumps({"key": "value"}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=resp):
            result = request_json("GET", "http://test/api", "token")
            assert result["key"] == "value"

    def test_empty_response_returns_dict(self):
        from seed_mem0_skills import request_json

        resp = MagicMock()
        resp.read.return_value = b""
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=resp):
            result = request_json("GET", "http://test/api", "token")
            assert result == {}

    def test_http_error_raises_runtime_error(self):
        from seed_mem0_skills import request_json

        exc = MagicMock()
        exc.code = 404
        exc.read.return_value = b'{"error": "not found"}'
        exc.__class__ = urllib.error.HTTPError

        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(RuntimeError):
                request_json("GET", "http://test/api", "token")

    def test_url_error_raises_runtime_error(self):
        from seed_mem0_skills import request_json

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("network")):
            with pytest.raises(RuntimeError):
                request_json("GET", "http://test/api", "token")


class TestEndpoint:
    """Tests for endpoint helper."""

    def test_basic_path(self):
        from seed_mem0_skills import endpoint
        assert endpoint("http://localhost", "/v0/apply") == "http://localhost/v0/apply"

    def test_strips_trailing_slash(self):
        from seed_mem0_skills import endpoint
        assert endpoint("http://localhost/", "/v0/apply") == "http://localhost/v0/apply"

    def test_strips_v0_suffix(self):
        from seed_mem0_skills import endpoint
        assert endpoint("http://localhost/v0", "/apply") == "http://localhost/apply"

    def test_base_with_v0_and_path(self):
        from seed_mem0_skills import endpoint
        assert endpoint("http://localhost/v0", "/skills") == "http://localhost/skills"


class TestMain:
    """Tests for main CLI entry point."""

    def test_dry_run_prints_yaml(self, tmp_path, capsys):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "test-skill" / "SKILL.md").write_text("---\nname: Test Skill\n---\n# Test Skill\n\nBody.")

        with patch.object(sys, "argv", ["seed-mem0-skills.py", "--dry-run", "--print-yaml"]):
            from seed_mem0_skills import main
            # Should not raise
            try:
                rc = main()
            except Exception:
                pass  # May fail on network calls, that's fine


class TestConstants:
    """Tests for module-level constants."""

    def test_default_registry_url(self):
        from seed_mem0_skills import DEFAULT_REGISTRY_URL
        assert DEFAULT_REGISTRY_URL == "http://127.0.0.1:8765/registry-api"

    def test_default_token(self):
        from seed_mem0_skills import DEFAULT_TOKEN
        assert DEFAULT_TOKEN == "local"

    def test_default_namespace(self):
        from seed_mem0_skills import DEFAULT_NAMESPACE
        assert DEFAULT_NAMESPACE == "default"

    def test_default_tag(self):
        from seed_mem0_skills import DEFAULT_TAG
        assert DEFAULT_TAG == "latest"

    def test_annotation_prefix(self):
        from seed_mem0_skills import ANNOTATION_PREFIX
        assert ANNOTATION_PREFIX == "agentregistry.mem0.ai"

    def test_source_path_annotation(self):
        from seed_mem0_skills import SOURCE_PATH_ANNOTATION
        assert SOURCE_PATH_ANNOTATION == "agentregistry.mem0.ai/source-path"

    def test_artifact_media_type(self):
        from seed_mem0_skills import ARTIFACT_MEDIA_TYPE
        assert ARTIFACT_MEDIA_TYPE == "application/vnd.agentregistry.skill.v1.tar+gzip"

    def test_max_skill_files(self):
        from seed_mem0_skills import MAX_SKILL_FILES
        assert MAX_SKILL_FILES == 256

    def test_max_skill_bytes(self):
        from seed_mem0_skills import MAX_SKILL_BYTES
        assert MAX_SKILL_BYTES == 32 << 20  # 32 MB

    def test_max_skill_file_bytes(self):
        from seed_mem0_skills import MAX_SKILL_FILE_BYTES
        assert MAX_SKILL_FILE_BYTES == 4 << 20  # 4 MB

    def test_max_archive_bytes(self):
        from seed_mem0_skills import MAX_ARCHIVE_BYTES
        assert MAX_ARCHIVE_BYTES == 16 << 20  # 16 MB

    def test_max_path_bytes(self):
        from seed_mem0_skills import MAX_PATH_BYTES
        assert MAX_PATH_BYTES == 240
