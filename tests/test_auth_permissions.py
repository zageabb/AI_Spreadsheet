"""Tests for authentication and workbook permission workflows."""

from __future__ import annotations

import pytest

from app.auth.service import AuthService, InMemoryUserRepository, PasswordHasher, SessionTokenManager
from app.models.workbook import Workbook
from app.permissions.service import PermissionService


def _build_auth_service() -> AuthService:
    return AuthService(
        repository=InMemoryUserRepository(),
        password_hasher=PasswordHasher(iterations=1000),
        session_manager=SessionTokenManager(secret="unit-test-secret", ttl_seconds=3600),
    )


def test_auth_register_login_and_validate_session(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", "unit-test-secret")
    auth = _build_auth_service()

    user = auth.register_user("Owner@Example.com", "secret-pass")
    assert user.email == "owner@example.com"
    assert user.password_hash.startswith("pbkdf2_sha256$")

    token = auth.login("owner@example.com", "secret-pass")
    principal = auth.validate_session(token)

    assert principal is not None
    assert principal.email == "owner@example.com"
    assert principal.user_id == user.user_id


def test_auth_login_rejects_bad_password(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", "unit-test-secret")
    auth = _build_auth_service()
    auth.register_user("viewer@example.com", "correct-pass")

    with pytest.raises(ValueError):
        auth.login("viewer@example.com", "wrong-pass")


def test_password_hasher_rejects_malformed_hash():
    hasher = PasswordHasher(iterations=1000)
    assert not hasher.verify_password("secret-pass", "not-a-valid-hash")


def test_session_token_manager_rejects_tampered_token():
    manager = SessionTokenManager(secret="unit-test-secret", ttl_seconds=3600)
    auth = _build_auth_service()
    user = auth.register_user("owner@example.com", "secret-pass")
    token = manager.issue_token(user)
    tampered = token + "tamper"

    assert manager.validate_token(tampered) is None


def test_auth_register_rejects_invalid_email_type(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", "unit-test-secret")
    auth = _build_auth_service()

    with pytest.raises(ValueError):
        auth.register_user(None, "secret-pass")  # type: ignore[arg-type]


def test_permission_workflow_owner_editor_viewer_and_revoke():
    permissions = PermissionService()
    workbook = permissions.create_workbook_with_owner("Roadmap", "owner@example.com")

    workbook.permissions = permissions.invite_user_as_owner(
        workbook.permissions,
        actor_email="owner@example.com",
        user_email="viewer@example.com",
    )
    workbook.permissions = permissions.grant_editor_access_as_owner(
        workbook.permissions,
        actor_email="owner@example.com",
        user_email="editor@example.com",
    )

    assert permissions.resolve_role("owner@example.com", workbook) == "owner"
    assert permissions.resolve_role("editor@example.com", workbook) == "editor"
    assert permissions.resolve_role("viewer@example.com", workbook) == "viewer"

    assert permissions.can_edit("owner@example.com", workbook)
    assert permissions.can_edit("editor@example.com", workbook)
    assert not permissions.can_edit("viewer@example.com", workbook)
    assert permissions.can_view("viewer@example.com", workbook)

    workbook.permissions = permissions.revoke_access_as_owner(
        workbook.permissions,
        actor_email="owner@example.com",
        user_email="viewer@example.com",
    )
    assert permissions.resolve_role("viewer@example.com", workbook) is None


def test_permission_service_rejects_non_owner_sharing_changes():
    service = PermissionService()
    workbook = Workbook(name="Ops", permissions={"owner": "owner@example.com", "shared_with": []})

    with pytest.raises(PermissionError):
        service.grant_viewer_access_as_owner(
            permissions=workbook.permissions,
            actor_email="editor@example.com",
            user_email="viewer@example.com",
        )


def test_permission_service_rejects_revoking_owner():
    service = PermissionService()
    workbook = Workbook(name="Ops", permissions={"owner": "owner@example.com", "shared_with": []})

    with pytest.raises(ValueError):
        service.revoke_access(workbook.permissions, "owner@example.com")


def test_permission_service_rejects_invalid_email_type():
    service = PermissionService()

    with pytest.raises(ValueError):
        service.grant_viewer_access({"owner": "owner@example.com", "shared_with": []}, None)  # type: ignore[arg-type]
