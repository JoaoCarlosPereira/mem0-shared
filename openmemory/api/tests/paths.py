"""Resolve openmemory/ root in local checkout and Docker test runs."""

from __future__ import annotations

from pathlib import Path


def openmemory_root() -> Path:
    """Return the directory containing docker-compose.scale.yml."""
    here = Path(__file__).resolve().parent
    for candidate in (here.parent, *here.parents):
        if (candidate / "docker-compose.scale.yml").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate openmemory root (missing docker-compose.scale.yml). "
        "Ensure compose artifacts are present in the Docker image or checkout."
    )
