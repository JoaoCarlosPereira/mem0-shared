import gzip
import io
import tarfile

import pytest

from app.services.skill_packages import SkillFileInput, SkillPackageInput, build_skill_archive


def test_build_skill_archive_preserves_complete_tree_and_modes():
    payload = SkillPackageInput(
        name="skill-pt",
        description="Skill para revisar código da equipe em português.",
        files=[
            SkillFileInput(
                path="SKILL.md",
                content="# Revisão de código\n\nUse estas instruções.",
            ),
            SkillFileInput(
                path="scripts/verificar.py",
                content="print('ok')",
                mode=0o755,
            ),
            SkillFileInput(
                path="assets/logo.bin",
                content="AAECAw==",
                encoding="base64",
            ),
        ],
    )

    archive, inventory = build_skill_archive(payload)

    assert [item["path"] for item in inventory] == [
        "SKILL.md",
        "assets/logo.bin",
        "scripts/verificar.py",
    ]
    with gzip.GzipFile(fileobj=io.BytesIO(archive)) as gz, tarfile.open(fileobj=gz, mode="r:") as tar:
        entries = {entry.name: (tar.extractfile(entry).read(), entry.mode) for entry in tar if entry.isfile()}
    assert entries["assets/logo.bin"][0] == b"\x00\x01\x02\x03"
    assert entries["scripts/verificar.py"][1] == 0o755


@pytest.mark.parametrize(
    "files, message",
    [
        ([SkillFileInput(path="README.md", content="Texto em português")], "SKILL.md"),
        ([SkillFileInput(path="SKILL.md", content="English instructions only")], "PT-BR"),
        ([SkillFileInput(path="SKILL.md", content="# válido"), SkillFileInput(path="../escape.txt", content="x")], "caminho"),
    ],
)
def test_build_skill_archive_rejects_invalid_skill(files, message):
    payload = SkillPackageInput(
        name="skill-pt",
        description="Uma descrição válida para a Skill da equipe.",
        files=files,
    )
    with pytest.raises(ValueError, match=message):
        build_skill_archive(payload)
