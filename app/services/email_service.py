"""Modular email notification services for sharing and auth events."""

from __future__ import annotations

import os
import json
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as SMTPEmailMessage
from pathlib import Path
from string import Template
from typing import Protocol
from urllib import error, request


@dataclass(slots=True)
class OutboundEmail:
    """Canonical outbound email message payload."""

    to_email: str
    subject: str
    text_body: str


@dataclass(slots=True)
class EmailSettings:
    """Environment-driven email delivery settings."""

    provider: str
    from_email: str
    enabled: bool
    dev_mode: bool
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_use_tls: bool
    api_endpoint: str
    api_token: str
    api_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "EmailSettings":
        settings = cls(
            provider=os.getenv("EMAIL_PROVIDER", "smtp").strip().lower(),
            from_email=os.getenv("EMAIL_FROM", "noreply@example.com").strip(),
            enabled=_env_flag("EMAIL_ENABLED", True),
            dev_mode=_env_flag("EMAIL_DEV_MODE", os.getenv("APP_ENV", "development") != "production"),
            smtp_host=os.getenv("SMTP_HOST", "localhost").strip(),
            smtp_port=int(os.getenv("SMTP_PORT", "1025")),
            smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
            smtp_use_tls=_env_flag("SMTP_USE_TLS", False),
            api_endpoint=os.getenv("EMAIL_API_ENDPOINT", "").strip(),
            api_token=os.getenv("EMAIL_API_TOKEN", "").strip(),
            api_timeout_seconds=int(os.getenv("EMAIL_API_TIMEOUT_SECONDS", "10")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.provider not in {"smtp", "api"}:
            raise ValueError("EMAIL_PROVIDER must be either 'smtp' or 'api'.")
        if "@" not in self.from_email:
            raise ValueError("EMAIL_FROM must be a valid email address.")
        if self.smtp_port <= 0 or self.api_timeout_seconds <= 0:
            raise ValueError("Email port and timeout values must be positive.")
        if self.enabled and not self.dev_mode:
            if self.provider == "smtp" and not self.smtp_host:
                raise ValueError("SMTP_HOST is required when SMTP delivery is enabled.")
            if self.provider == "api" and not self.api_endpoint:
                raise ValueError("EMAIL_API_ENDPOINT is required when API delivery is enabled.")


class EmailProvider(Protocol):
    """Provider abstraction for swappable delivery backends."""

    def send(self, message: OutboundEmail) -> None:
        """Deliver a single outbound email message."""


class SMTPEmailProvider:
    """SMTP-based email provider implementation."""

    def __init__(self, settings: EmailSettings) -> None:
        self.settings = settings

    def send(self, message: OutboundEmail) -> None:
        mime_message = SMTPEmailMessage()
        mime_message["From"] = self.settings.from_email
        mime_message["To"] = message.to_email
        mime_message["Subject"] = message.subject
        mime_message.set_content(message.text_body)

        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=self.settings.api_timeout_seconds) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(mime_message)


class APIEmailProvider:
    """HTTP API-backed provider scaffold (generic JSON webhook)."""

    def __init__(self, settings: EmailSettings) -> None:
        if not settings.api_endpoint:
            raise ValueError("EMAIL_API_ENDPOINT must be set for api provider.")
        self.settings = settings

    def send(self, message: OutboundEmail) -> None:
        payload = json.dumps(
            {"from": self.settings.from_email, "to": message.to_email,
             "subject": message.subject, "text": message.text_body}
        ).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.settings.api_token:
            headers["Authorization"] = f"Bearer {self.settings.api_token}"

        req = request.Request(
            self.settings.api_endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.settings.api_timeout_seconds):
                return
        except error.URLError as exc:
            raise RuntimeError(f"Email API provider failed to send message: {exc}") from exc


class DevNullEmailProvider:
    """Safe development provider that captures messages in memory and prints logs."""

    def __init__(self) -> None:
        self.sent_messages: list[OutboundEmail] = []

    def send(self, message: OutboundEmail) -> None:
        self.sent_messages.append(message)
        print(
            "[email:dev-mode] "
            f"to={message.to_email} subject={message.subject!r} body_preview={message.text_body[:80]!r}"
        )


class EmailTemplateRenderer:
    """Loads and renders text templates from app/services/email_templates/."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or Path(__file__).with_name("email_templates")

    def render(self, template_name: str, **context: str) -> str:
        template_path = self.templates_dir / f"{template_name}.txt"
        template_text = template_path.read_text(encoding="utf-8")
        return Template(template_text).safe_substitute(**context)


class EmailNotificationService:
    """Composes templates + provider for workbook/auth email notifications."""

    def __init__(
        self,
        settings: EmailSettings | None = None,
        provider: EmailProvider | None = None,
        renderer: EmailTemplateRenderer | None = None,
    ) -> None:
        self.settings = settings or EmailSettings.from_env()
        self.provider = provider or self._build_provider(self.settings)
        self.renderer = renderer or EmailTemplateRenderer()

    def send_workbook_invitation(
        self,
        recipient_email: str,
        workbook_name: str,
        inviter_email: str,
        role: str,
        workbook_link: str = "",
    ) -> None:
        body = self.renderer.render(
            "workbook_invitation",
            recipient_email=recipient_email,
            workbook_name=workbook_name,
            inviter_email=inviter_email,
            role=role,
            workbook_link=workbook_link or "(not configured)",
        )
        self._send(
            OutboundEmail(
                to_email=recipient_email,
                subject=f"You've been invited to '{workbook_name}'",
                text_body=body,
            )
        )

    def send_access_granted(
        self,
        recipient_email: str,
        workbook_name: str,
        granted_by_email: str,
        role: str,
        workbook_link: str = "",
    ) -> None:
        body = self.renderer.render(
            "access_granted",
            recipient_email=recipient_email,
            workbook_name=workbook_name,
            granted_by_email=granted_by_email,
            role=role,
            workbook_link=workbook_link or "(not configured)",
        )
        self._send(
            OutboundEmail(
                to_email=recipient_email,
                subject=f"Access granted: '{workbook_name}'",
                text_body=body,
            )
        )

    def send_access_removed(
        self,
        recipient_email: str,
        workbook_name: str,
        removed_by_email: str,
    ) -> None:
        body = self.renderer.render(
            "access_removed",
            recipient_email=recipient_email,
            workbook_name=workbook_name,
            removed_by_email=removed_by_email,
        )
        self._send(
            OutboundEmail(
                to_email=recipient_email,
                subject=f"Access removed: '{workbook_name}'",
                text_body=body,
            )
        )

    def send_password_reset_scaffold(self, recipient_email: str, reset_token: str, reset_link_base: str = "") -> None:
        """Optional reset scaffold for later auth UI/server integration."""
        reset_link = f"{reset_link_base.rstrip('/')}/reset-password?token={reset_token}" if reset_link_base else "(not configured)"
        body = self.renderer.render(
            "password_reset",
            recipient_email=recipient_email,
            reset_token=reset_token,
            reset_link=reset_link,
        )
        self._send(
            OutboundEmail(
                to_email=recipient_email,
                subject="Password reset instructions",
                text_body=body,
            )
        )

    def _send(self, message: OutboundEmail) -> None:
        if not self.settings.enabled:
            return
        if "@" not in message.to_email or "\n" in message.to_email or "\r" in message.to_email:
            raise ValueError("Recipient email address is invalid.")
        self.provider.send(message)

    def _build_provider(self, settings: EmailSettings) -> EmailProvider:
        if settings.dev_mode:
            return DevNullEmailProvider()
        if settings.provider == "smtp":
            return SMTPEmailProvider(settings)
        if settings.provider == "api":
            return APIEmailProvider(settings)
        raise ValueError("Unsupported EMAIL_PROVIDER. Use 'smtp' or 'api'.")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
