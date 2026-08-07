"""Public passthrough for the immutable Skill artifact.

Install recipes verify the published digest, so the artifact route must hand
back the stored bytes untouched. ``/download`` rebuilds a ZIP and hashes
differently; these tests pin that the two routes stay distinct.
"""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import store as store_router
from app.services.store_recipes import SKILL_ARTIFACT_MEDIA_TYPE

RAW_ARTIFACT = b"\x1f\x8b\x08\x00raw-tar-gz-bytes-not-a-zip"
RAW_DIGEST = hashlib.sha256(RAW_ARTIFACT).hexdigest()


def _rezipped() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("SKILL.md", "# skill\n")
    return buffer.getvalue()


class FakeRegistryClient:
    def __init__(self):
        self.artifact_calls: list[tuple[str, str]] = []

    async def get_skill_artifact(self, *, name, tag, namespace="default", auth_headers=None):
        self.artifact_calls.append((name, tag))
        return RAW_ARTIFACT, {
            "digest": "sha-256=stub",
            "etag": '"stub"',
            "content-disposition": 'attachment; filename="team-skill-v1.tar.gz"',
        }

    async def get_skill_download(self, *, name, tag, namespace="default", auth_headers=None):
        return _rezipped(), {}


@pytest.fixture
def client(monkeypatch):
    registry = FakeRegistryClient()
    app = FastAPI()
    app.include_router(store_router.router)
    app.dependency_overrides[store_router.get_registry_client] = lambda: registry
    monkeypatch.setattr(store_router, "_current_actor_id", lambda: "test-actor")
    monkeypatch.setattr(store_router, "_registry_auth_headers", lambda request: None)
    with TestClient(app) as test_client:
        test_client.registry = registry
        yield test_client


def test_artifact_route_returns_stored_bytes_unchanged(client):
    response = client.get("/api/v1/store/skills/team-skill/v1/artifact")

    assert response.status_code == 200
    assert response.content == RAW_ARTIFACT
    assert hashlib.sha256(response.content).hexdigest() == RAW_DIGEST
    assert response.headers["x-skill-sha256"] == RAW_DIGEST
    assert client.registry.artifact_calls == [("team-skill", "v1")]


def test_artifact_route_announces_tar_gzip_and_forwards_validators(client):
    response = client.get("/api/v1/store/skills/team-skill/v1/artifact")

    assert response.headers["content-type"] == SKILL_ARTIFACT_MEDIA_TYPE
    assert response.headers["digest"] == "sha-256=stub"
    assert response.headers["etag"] == '"stub"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].endswith('.tar.gz"')


def test_download_route_stays_a_distinct_rezipped_payload(client):
    artifact = client.get("/api/v1/store/skills/team-skill/v1/artifact")
    download = client.get("/api/v1/store/skills/team-skill/v1/download")

    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert download.content != artifact.content
    assert download.content.startswith(b"PK")
