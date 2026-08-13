from unittest.mock import MagicMock
from uuid import uuid4

from app.utils.logging_context import (
    auth_email_var,
    auth_method_var,
    auth_user_var,
)
from app.utils.spec_auth import resolve_spec_actor


def test_resolve_spec_actor_uses_session_display_name():
    user_id = uuid4()
    user = MagicMock(
        display_name="João Carlos",
        name="João",
        email="joao@example.com",
    )
    db = MagicMock()
    db.query().filter().first.return_value = user
    method_token = auth_method_var.set("session")
    user_token = auth_user_var.set(str(user_id))
    email_token = auth_email_var.set("joao@example.com")
    try:
        assert resolve_spec_actor(db=db) == "João Carlos"
    finally:
        auth_email_var.reset(email_token)
        auth_user_var.reset(user_token)
        auth_method_var.reset(method_token)


def test_resolve_spec_actor_falls_back_to_session_email_without_db():
    method_token = auth_method_var.set("session")
    email_token = auth_email_var.set("joao@example.com")
    try:
        assert resolve_spec_actor() == "joao@example.com"
    finally:
        auth_email_var.reset(email_token)
        auth_method_var.reset(method_token)
