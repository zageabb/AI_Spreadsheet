"""Authentication services for email/password login and session handling."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from app.services.email_service import EmailNotificationService
from app.storage.postgres_config import PostgresConfig
from app.storage.postgres_db import PostgresDatabase


@dataclass(slots=True)
class UserRecord:
    """Stored user identity record."""

    user_id: str
    email: str
    password_hash: str


@dataclass(slots=True)
class SessionPrincipal:
    """Represents an authenticated session principal."""

    user_id: str
    email: str
    issued_at: int
    expires_at: int


class UserRepository(Protocol):
    """Auth repository abstraction for multiple storage backends."""

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        """Create and return a new user."""

    def get_user_by_email(self, email: str) -> UserRecord | None:
        """Return user for the email when present."""


class InMemoryUserRepository:
    """Simple repository scaffold for non-database auth workflows."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, UserRecord] = {}

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        normalized_email = _normalize_email(email)
        if normalized_email in self._users_by_email:
            raise ValueError("User already exists for this email address.")

        user = UserRecord(user_id=secrets.token_hex(16), email=normalized_email, password_hash=password_hash)
        self._users_by_email[normalized_email] = user
        return user

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._users_by_email.get(_normalize_email(email))


class JsonUserRepository:
    """Persistent local identity repository containing password hashes only."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        normalized_email = _normalize_email(email)
        with self._lock:
            users = self._read_users()
            if normalized_email in users:
                raise ValueError("User already exists for this email address.")
            user = UserRecord(
                user_id=secrets.token_hex(16),
                email=normalized_email,
                password_hash=password_hash,
            )
            users[normalized_email] = user
            self._write_users(users)
            return user

    def get_user_by_email(self, email: str) -> UserRecord | None:
        with self._lock:
            return self._read_users().get(_normalize_email(email))

    def has_users(self) -> bool:
        """Return whether at least one local account has been registered."""
        with self._lock:
            return bool(self._read_users())

    def _read_users(self) -> dict[str, UserRecord]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Local identity store is unreadable: {self.path}") from exc
        raw_users = payload.get("users", []) if isinstance(payload, dict) else []
        users: dict[str, UserRecord] = {}
        for entry in raw_users if isinstance(raw_users, list) else []:
            if not isinstance(entry, dict):
                continue
            try:
                normalized = _normalize_email(entry.get("email"))
            except ValueError:
                continue
            user_id = str(entry.get("user_id") or "").strip()
            password_hash = str(entry.get("password_hash") or "")
            if user_id and password_hash:
                users[normalized] = UserRecord(user_id, normalized, password_hash)
        return users

    def _write_users(self, users: dict[str, UserRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        payload = {
            "schema_version": 1,
            "users": [
                {
                    "user_id": user.user_id,
                    "email": user.email,
                    "password_hash": user.password_hash,
                }
                for user in sorted(users.values(), key=lambda item: item.email)
            ],
        }
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(self.path)


class PostgresUserRepository:
    """PostgreSQL-backed user repository for registration/login flows."""

    def __init__(self, config: PostgresConfig | None = None) -> None:
        self.db = PostgresDatabase(config=config)

    def create_user(self, email: str, password_hash: str) -> UserRecord:
        normalized_email = _normalize_email(email)
        with self.db.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash)
                    VALUES (%s, %s)
                    ON CONFLICT (email) DO UPDATE
                    SET password_hash = EXCLUDED.password_hash
                    WHERE users.password_hash IS NULL OR users.password_hash = ''
                    RETURNING id, email, password_hash
                    """,
                    (normalized_email, password_hash),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("User already exists for this email address.")
        return UserRecord(
            user_id=str(row["id"]),
            email=str(row["email"]),
            password_hash=str(row["password_hash"] or ""),
        )

    def get_user_by_email(self, email: str) -> UserRecord | None:
        normalized_email = _normalize_email(email)
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, password_hash FROM users WHERE email = %s LIMIT 1",
                    (normalized_email,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return UserRecord(
                    user_id=str(row["id"]),
                    email=str(row["email"]),
                    password_hash=str(row["password_hash"] or ""),
                )


class PasswordHasher:
    """PBKDF2 password hashing utility with env-configurable strength."""

    def __init__(self, iterations: int | None = None, pepper: str | None = None) -> None:
        configured_iterations = iterations if iterations is not None else int(os.getenv("AUTH_PASSWORD_ITERATIONS", "260000"))
        if configured_iterations <= 0:
            raise ValueError("AUTH_PASSWORD_ITERATIONS must be a positive integer.")

        self.iterations = configured_iterations
        self.pepper = pepper if pepper is not None else os.getenv("AUTH_PASSWORD_PEPPER", "")

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            f"{password}{self.pepper}".encode("utf-8"),
            salt,
            self.iterations,
        )
        return f"pbkdf2_sha256${self.iterations}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            algorithm, iteration_text, salt_text, digest_text = password_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False

            iterations = int(iteration_text)
            if iterations <= 0:
                return False
            salt = base64.urlsafe_b64decode(salt_text.encode())
            expected_digest = base64.urlsafe_b64decode(digest_text.encode())
        except (TypeError, ValueError):
            return False
        current_digest = hashlib.pbkdf2_hmac(
            "sha256",
            f"{password}{self.pepper}".encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(current_digest, expected_digest)


class SessionTokenManager:
    """Signs and validates lightweight bearer tokens for desktop sessions."""

    def __init__(self, secret: str | None = None, ttl_seconds: int | None = None) -> None:
        self.secret = (secret if secret is not None else os.getenv("AUTH_SESSION_SECRET", "")).encode("utf-8")
        if not self.secret:
            raise ValueError("AUTH_SESSION_SECRET must be configured for session token handling.")
        configured_ttl = ttl_seconds if ttl_seconds is not None else int(os.getenv("AUTH_SESSION_TTL_SECONDS", "28800"))
        if configured_ttl <= 0:
            raise ValueError("AUTH_SESSION_TTL_SECONDS must be a positive integer.")
        self.ttl_seconds = configured_ttl

    def issue_token(self, user: UserRecord) -> str:
        issued_at = int(time.time())
        payload = {
            "user_id": user.user_id,
            "email": user.email,
            "iat": issued_at,
            "exp": issued_at + self.ttl_seconds,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
        signature = self._sign(encoded_payload.encode("ascii"))
        return f"{encoded_payload}.{signature}"

    def validate_token(self, token: str) -> SessionPrincipal | None:
        try:
            encoded_payload, signature = token.split(".", 1)
        except ValueError:
            return None

        if not hmac.compare_digest(self._sign(encoded_payload.encode("ascii")), signature):
            return None

        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded_payload.encode("ascii")))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

        try:
            expires_at = int(payload.get("exp", 0))
            issued_at = int(payload.get("iat", 0))
        except (TypeError, ValueError):
            return None
        now = int(time.time())
        if expires_at <= now or issued_at <= 0 or issued_at > now + 60 or expires_at <= issued_at:
            return None

        user_id = str(payload.get("user_id") or "").strip()
        email = str(payload.get("email") or "").lower().strip()
        if not user_id or not email:
            return None

        return SessionPrincipal(
            user_id=user_id,
            email=email,
            issued_at=issued_at,
            expires_at=expires_at,
        )

    def _sign(self, payload: bytes) -> str:
        digest = hmac.new(self.secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii")


class IdentityProvider(Protocol):
    """Abstraction seam for future external identity providers."""

    def register(self, email: str, password: str) -> UserRecord:
        """Register user credentials with the identity provider."""

    def authenticate(self, email: str, password: str) -> UserRecord:
        """Return user record when credentials are valid."""


class LocalIdentityProvider:
    """Email/password provider backed by a UserRepository and PasswordHasher."""

    def __init__(self, repository: UserRepository, password_hasher: PasswordHasher) -> None:
        self.repository = repository
        self.password_hasher = password_hasher

    def register(self, email: str, password: str) -> UserRecord:
        normalized_email = _normalize_email(email)
        _validate_password(password)
        password_hash = self.password_hasher.hash_password(password)
        return self.repository.create_user(email=normalized_email, password_hash=password_hash)

    def authenticate(self, email: str, password: str) -> UserRecord:
        user = self.repository.get_user_by_email(email)
        if user is None:
            raise ValueError("Invalid email or password.")

        if not user.password_hash or not self.password_hasher.verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password.")

        return user


class AuthService:
    """Registration/login/session auth service using email identity."""

    def __init__(
        self,
        repository: UserRepository | None = None,
        password_hasher: PasswordHasher | None = None,
        session_manager: SessionTokenManager | None = None,
        identity_provider: IdentityProvider | None = None,
    ) -> None:
        self.repository = repository or InMemoryUserRepository()
        self.password_hasher = password_hasher or PasswordHasher()
        self.identity_provider = identity_provider or LocalIdentityProvider(self.repository, self.password_hasher)
        self.session_manager = session_manager or SessionTokenManager()

    def register_user(self, email: str, password: str) -> UserRecord:
        """Create a user identity from email/password credentials."""
        return self.identity_provider.register(email=email, password=password)

    def login(self, email: str, password: str) -> str:
        """Authenticate by email+password and return a signed session token."""
        user = self.identity_provider.authenticate(email=email, password=password)
        return self.session_manager.issue_token(user)

    def send_password_reset_email(
        self,
        email: str,
        email_service: EmailNotificationService | None = None,
        reset_link_base: str = "",
    ) -> str:
        """
        Optional password reset scaffold for future server/UI integration.

        Returns an opaque token so a future reset-token repository can persist it.
        """
        user = self.repository.get_user_by_email(email)
        if user is None:
            raise ValueError("No user exists for this email address.")

        token = secrets.token_urlsafe(24)
        notifier = email_service or EmailNotificationService()
        notifier.send_password_reset_scaffold(
            recipient_email=user.email,
            reset_token=token,
            reset_link_base=reset_link_base,
        )
        return token

    def validate_session(self, token: str) -> SessionPrincipal | None:
        """Validate token and return principal when token is valid."""
        return self.session_manager.validate_token(token)


def create_auth_service() -> AuthService:
    """Build the configured desktop authentication service.

    JSON mode stores hashed local accounts in ``AUTH_USER_STORE``. PostgreSQL
    mode uses the shared users table. A random in-process signing key keeps the
    zero-configuration desktop path usable; configure ``AUTH_SESSION_SECRET``
    when sessions must survive across processes.
    """
    provider = os.getenv("AUTH_IDENTITY_PROVIDER", "local").strip().lower()
    if provider != "local":
        raise ValueError(f"AUTH_IDENTITY_PROVIDER is not configured: {provider}")

    backend = os.getenv("STORAGE_BACKEND", "json").strip().lower()
    if backend == "postgres":
        repository: UserRepository = PostgresUserRepository()
    elif backend == "json":
        repository = JsonUserRepository(os.getenv("AUTH_USER_STORE", "./data/users.json"))
    else:
        raise ValueError("STORAGE_BACKEND must be either 'json' or 'postgres'.")

    configured_secret = os.getenv("AUTH_SESSION_SECRET", "").strip()
    if configured_secret == "replace_with_long_random_secret":
        configured_secret = ""
    if os.getenv("APP_ENV", "development").strip().lower() == "production" and len(configured_secret) < 32:
        raise ValueError("AUTH_SESSION_SECRET must contain at least 32 characters in production.")
    session_secret = configured_secret or secrets.token_urlsafe(32)
    return AuthService(
        repository=repository,
        session_manager=SessionTokenManager(secret=session_secret),
    )


def _normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise ValueError("A valid email address is required.")

    normalized = email.lower().strip()
    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
        or "." not in normalized.rsplit("@", 1)[1]
        or any(character.isspace() for character in normalized)
    ):
        raise ValueError("A valid email address is required.")
    return normalized


def _validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(password) > 1024:
        raise ValueError("Password is too long.")
