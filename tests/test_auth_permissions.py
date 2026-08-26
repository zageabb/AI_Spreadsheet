"""Tests for authentication and workbook permission workflows."""

from __future__ import annotations

import pytest

from app.auth.service import (
    AuthService,
    InMemoryUserRepository,
    JsonUserRepository,
    PasswordHasher,
    SessionTokenManager,
    create_auth_service,
)
from app.models.workbook import Workbook
from app.permissions.service import PermissionService, SharingWorkflowService


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


def test_json_user_repository_persists_only_hashed_credentials(tmp_path):
    path = tmp_path / "users.json"
    auth = AuthService(
        repository=JsonUserRepository(path),
        password_hasher=PasswordHasher(iterations=1000),
        session_manager=SessionTokenManager(secret="unit-test-secret"),
    )

    auth.register_user("Local@Example.com", "private-pass")
    reloaded = JsonUserRepository(path).get_user_by_email("local@example.com")

    assert reloaded is not None
    assert reloaded.email == "local@example.com"
    assert reloaded.password_hash.startswith("pbkdf2_sha256$")
    assert "private-pass" not in path.read_text(encoding="utf-8")


def test_transfer_ownership_keeps_previous_owner_as_editor():
    service = PermissionService()
    permissions = service.assign_owner({}, "owner@example.com")

    transferred = service.transfer_ownership(
        permissions,
        actor_email="owner@example.com",
        new_owner_email="new-owner@example.com",
    )

    workbook = Workbook(name="Plan", permissions=transferred)
    assert service.resolve_role("new-owner@example.com", workbook) == "owner"
    assert service.resolve_role("owner@example.com", workbook) == "editor"


def test_legacy_unowned_workbook_is_claimed_once():
    service = PermissionService()
    workbook = Workbook(name="Legacy")

    role, changed = service.resolve_or_claim("owner@example.com", workbook)
    other_role, changed_again = service.resolve_or_claim("other@example.com", workbook)

    assert role == "owner"
    assert changed is True
    assert other_role is None
    assert changed_again is False


def test_sharing_workflow_rejects_non_owner_grant():
    workbook = Workbook(
        name="Protected",
        permissions={
            "owner": "owner@example.com",
            "shared_with": [{"user": "editor@example.com", "role": "editor"}],
        },
    )
    workflow = SharingWorkflowService(permission_service=PermissionService())

    with pytest.raises(PermissionError, match="Only workbook owners"):
        workflow.grant_access(
            workbook,
            actor_email="editor@example.com",
            target_email="viewer@example.com",
            role="viewer",
        )


def test_auth_rejects_email_without_domain_suffix(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", "unit-test-secret")
    auth = _build_auth_service()

    with pytest.raises(ValueError, match="valid email"):
        auth.register_user("user@localhost", "private-pass")


def test_auth_factory_uses_persistent_json_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "json")
    monkeypatch.setenv("AUTH_USER_STORE", str(tmp_path / "identities.json"))
    monkeypatch.delenv("AUTH_SESSION_SECRET", raising=False)

    auth = create_auth_service()
    auth.register_user("owner@example.com", "private-pass")

    assert isinstance(auth.repository, JsonUserRepository)
    assert (tmp_path / "identities.json").is_file()


def test_auth_factory_requires_strong_production_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "json")
    monkeypatch.setenv("AUTH_USER_STORE", str(tmp_path / "identities.json"))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_SESSION_SECRET", "too-short")

    with pytest.raises(ValueError, match="32 characters"):
        create_auth_service()


def test_auth_factory_rejects_unconfigured_identity_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "json")
    monkeypatch.setenv("AUTH_USER_STORE", str(tmp_path / "identities.json"))
    monkeypatch.setenv("AUTH_IDENTITY_PROVIDER", "oidc")

    with pytest.raises(ValueError, match="not configured"):
        create_auth_service()
