"""Task_08: notices de licença do vendor PLANKA presentes no tree."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PLANKA = REPO / "integrations" / "planka"


def test_license_notices_present():
    assert (PLANKA / "LICENSE.md").is_file()
    licenses = PLANKA / "LICENSES"
    assert licenses.is_dir()
    names = {p.name for p in licenses.iterdir() if p.is_file()}
    assert "PLANKA Community License EN.md" in names
    assert "PLANKA License Guide EN.md" in names
    readme = (PLANKA / "README.mem0.md").read_text(encoding="utf-8")
    assert "Fair Use" in readme or "LICENSE" in readme or "licen" in readme.lower()


def test_cutover_runbook_exists():
    runbook = (
        REPO
        / "openmemory"
        / "docs"
        / "runbooks"
        / "planka-cutover-rollback.md"
    )
    assert runbook.is_file()
    text = runbook.read_text(encoding="utf-8")
    assert "down -v" in text
    assert "resync" in text.lower()
    assert "Fair Use" in text or "licen" in text.lower()
    assert "mem0_storage" in text
