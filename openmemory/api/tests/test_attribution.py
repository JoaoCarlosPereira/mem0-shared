"""Tests for payload attribution resolution (hostname vs user_id)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.utils.attribution import attribution_from_payload, author_hostname_from_payload


def test_author_from_hostname():
    assert author_hostname_from_payload({"hostname": "S0293"}) == "S0293"


def test_author_falls_back_to_user_id():
    assert author_hostname_from_payload({"user_id": "S0293"}) == "S0293"


def test_hostname_takes_priority_over_user_id():
    assert author_hostname_from_payload({"hostname": "S0293", "user_id": "S0296"}) == "S0293"


def test_missing_author_returns_none():
    assert author_hostname_from_payload({"project": "x"}) is None
    assert author_hostname_from_payload(None) is None


def test_attribution_from_payload_includes_client():
    out = attribution_from_payload({"hostname": "S0293", "mcp_client": "cursor"})
    assert out == {"created_by_hostname": "S0293", "created_by_client": "cursor"}
