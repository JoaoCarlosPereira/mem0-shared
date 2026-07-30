"""Session scope must isolate Last-k history by project (cross-session bleed fix)."""

from mem0.memory.main import _build_session_scope


def test_session_scope_includes_project():
    scope = _build_session_scope(
        {"user_id": "S0258", "project": "tarefa-366334"}
    )
    assert "user_id=S0258" in scope
    assert "project=tarefa-366334" in scope


def test_different_projects_get_different_scopes():
    a = _build_session_scope({"user_id": "S0258", "project": "ms-tributacao"})
    b = _build_session_scope({"user_id": "S0258", "project": "tarefa-366334"})
    assert a != b


def test_session_scope_without_project_still_works():
    scope = _build_session_scope({"user_id": "S0258"})
    assert scope == "user_id=S0258"
