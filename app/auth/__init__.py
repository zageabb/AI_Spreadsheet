"""Authentication module exports."""

from app.auth.service import (
    AuthService,
    IdentityProvider,
    InMemoryUserRepository,
    LocalIdentityProvider,
    PasswordHasher,
    PostgresUserRepository,
    SessionPrincipal,
    SessionTokenManager,
    UserRecord,
)

__all__ = [
    "AuthService",
    "IdentityProvider",
    "InMemoryUserRepository",
    "LocalIdentityProvider",
    "PasswordHasher",
    "PostgresUserRepository",
    "SessionPrincipal",
    "SessionTokenManager",
    "UserRecord",
]
"""Authentication exports."""

from app.auth.service import (
    AuthService,
    JsonUserRepository,
    SessionPrincipal,
    create_auth_service,
)

__all__ = ["AuthService", "JsonUserRepository", "SessionPrincipal", "create_auth_service"]
