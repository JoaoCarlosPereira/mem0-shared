"""Unit tests for Spec/PLANKA attachment tar collect/apply."""

import pytest

from app.utils.backup_attachments import (
    PLANKA_ARCNAME,
    SPEC_ARCNAME,
    apply_attachment_archive,
    collect_attachment_archives,
)


def test_collect_and_apply_round_trip(tmp_path):
    spec = tmp_path / "spec"
    planka = tmp_path / "planka"
    (spec / "t1").mkdir(parents=True)
    (spec / "t1" / "f.txt").write_text("hello", encoding="utf-8")
    (planka / "private").mkdir(parents=True)
    (planka / "private" / "x").write_bytes(b"abc")

    roots = {SPEC_ARCNAME: spec, PLANKA_ARCNAME: planka}
    archives = collect_attachment_archives(roots=roots)
    assert set(archives) == {SPEC_ARCNAME, PLANKA_ARCNAME}

    dest_spec = tmp_path / "out-spec"
    dest_planka = tmp_path / "out-planka"
    dest_roots = {SPEC_ARCNAME: dest_spec, PLANKA_ARCNAME: dest_planka}
    apply_attachment_archive(SPEC_ARCNAME, archives[SPEC_ARCNAME], roots=dest_roots)
    apply_attachment_archive(PLANKA_ARCNAME, archives[PLANKA_ARCNAME], roots=dest_roots)

    assert (dest_spec / "t1" / "f.txt").read_text(encoding="utf-8") == "hello"
    assert (dest_planka / "private" / "x").read_bytes() == b"abc"


def test_collect_missing_dir_yields_empty_tar(tmp_path):
    roots = {
        SPEC_ARCNAME: tmp_path / "missing-spec",
        PLANKA_ARCNAME: tmp_path / "missing-planka",
    }
    archives = collect_attachment_archives(roots=roots)
    assert len(archives[SPEC_ARCNAME]) > 0  # gzip header still present
    dest = tmp_path / "empty-out"
    apply_attachment_archive(SPEC_ARCNAME, archives[SPEC_ARCNAME], roots={SPEC_ARCNAME: dest})
    assert dest.is_dir()
    assert list(dest.iterdir()) == []


def test_apply_rejects_path_traversal(tmp_path):
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="../evil.txt")
        data = b"x"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    dest = tmp_path / "safe"
    dest.mkdir()
    with pytest.raises(ValueError, match="inseguro"):
        apply_attachment_archive(
            SPEC_ARCNAME, buf.getvalue(), roots={SPEC_ARCNAME: dest}
        )


def test_apply_clears_stale_files(tmp_path):
    root = tmp_path / "vol"
    root.mkdir()
    (root / "stale.txt").write_text("old", encoding="utf-8")
    fresh = tmp_path / "src"
    fresh.mkdir()
    (fresh / "new.txt").write_text("new", encoding="utf-8")
    archives = collect_attachment_archives(
        roots={SPEC_ARCNAME: fresh, PLANKA_ARCNAME: tmp_path / "p"}
    )
    apply_attachment_archive(
        SPEC_ARCNAME, archives[SPEC_ARCNAME], roots={SPEC_ARCNAME: root}
    )
    assert (root / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (root / "stale.txt").exists()
