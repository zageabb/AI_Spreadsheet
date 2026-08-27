"""Tests for modular email notification workflows."""

from __future__ import annotations

from app.auth.service import (
    AuthService, InMemoryUserRepository, PasswordHasher,
    PasswordResetTokenManager, SessionTokenManager,
)
from app.models.workbook import Workbook
from app.permissions.service import PermissionService, SharingWorkflowService
from app.services.email_service import DevNullEmailProvider, EmailNotificationService, EmailSettings


def _dev_email_service() -> tuple[EmailNotificationService, DevNullEmailProvider]:
    provider = DevNullEmailProvider()
    settings = EmailSettings(
        provider="smtp",
        from_email="noreply@example.com",
        enabled=True,
        dev_mode=True,
        smtp_host="localhost",
        smtp_port=1025,
        smtp_username="",
        smtp_password="",
        smtp_use_tls=False,
        api_endpoint="",
        api_token="",
        api_timeout_seconds=5,
    )
    return EmailNotificationService(settings=settings, provider=provider), provider


def test_sharing_workflow_sends_invite_and_revoke_notifications():
    notifier, outbox = _dev_email_service()
    workflow = SharingWorkflowService(permission_service=PermissionService(), email_service=notifier)
    workbook = Workbook(name="Q2 Plan", permissions={"owner": "owner@example.com", "shared_with": []})

    workflow.invite_user(
        workbook=workbook,
        actor_email="owner@example.com",
        target_email="viewer@example.com",
        role="viewer",
        workbook_link="http://localhost/workbooks/q2-plan",
    )
    workflow.revoke_access(workbook=workbook, actor_email="owner@example.com", target_email="viewer@example.com")

    assert len(outbox.sent_messages) == 2
    assert outbox.sent_messages[0].to_email == "viewer@example.com"
    assert "invited" in outbox.sent_messages[0].subject.lower()
    assert "access removed" in outbox.sent_messages[1].subject.lower()


def test_auth_password_reset_scaffold_sends_notification(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", "unit-test-secret")

    auth = AuthService(
        repository=InMemoryUserRepository(),
        password_hasher=PasswordHasher(iterations=1000),
        session_manager=SessionTokenManager(secret="unit-test-secret", ttl_seconds=3600),
    )
    auth.register_user("member@example.com", "secret-pass")

    notifier, outbox = _dev_email_service()
    token = auth.send_password_reset_email(
        email="member@example.com",
        email_service=notifier,
        reset_link_base="http://localhost:8000",
    )

    assert token
    assert len(outbox.sent_messages) == 1
    assert outbox.sent_messages[0].to_email == "member@example.com"
    assert "password reset" in outbox.sent_messages[0].subject.lower()


def test_password_reset_changes_credentials_and_token_cannot_be_replayed():
    auth = AuthService(
        repository=InMemoryUserRepository(),
        password_hasher=PasswordHasher(iterations=1000),
        session_manager=SessionTokenManager(secret="unit-test-secret", ttl_seconds=3600),
        reset_token_manager=PasswordResetTokenManager(secret="reset-secret", ttl_seconds=300),
    )
    auth.register_user("member@example.com", "old-secret")
    notifier, _ = _dev_email_service()
    token = auth.send_password_reset_email("member@example.com", notifier)

    auth.reset_password("member@example.com", token, "new-secret")

    assert auth.validate_session(auth.login("member@example.com", "new-secret")) is not None
    try:
        auth.login("member@example.com", "old-secret")
    except ValueError:
        pass
    else:
        raise AssertionError("Old credentials unexpectedly remained valid")

    try:
        auth.reset_password("member@example.com", token, "another-secret")
    except ValueError:
        pass
    else:
        raise AssertionError("A consumed reset token was accepted again")


def test_sharing_workflow_rolls_back_permissions_when_delivery_fails():
    class FailingProvider:
        def send(self, _message):
            raise RuntimeError("delivery unavailable")

    settings = EmailSettings(
        provider="smtp", from_email="noreply@example.com", enabled=True, dev_mode=False,
        smtp_host="localhost", smtp_port=25, smtp_username="", smtp_password="",
        smtp_use_tls=False, api_endpoint="", api_token="", api_timeout_seconds=5,
    )
    workflow = SharingWorkflowService(
        email_service=EmailNotificationService(settings=settings, provider=FailingProvider())
    )
    workbook = Workbook(name="Plan", permissions={"owner": "owner@example.com", "shared_with": []})

    try:
        workflow.grant_access(workbook, "owner@example.com", "viewer@example.com", "viewer")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected delivery failure")

    assert workbook.permissions["shared_with"] == []
