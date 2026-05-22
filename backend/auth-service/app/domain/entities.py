"""Auth Service - Domain Entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class AuthUser:
    """Authentication user aggregate root."""
    
    id: UUID
    email: str
    password_hash: str
    is_active: bool = True
    is_verified: bool = False
    last_login_at: Optional[datetime] = None
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(email: str, password_hash: str) -> "AuthUser":
        """Factory method to create a new AuthUser."""
        return AuthUser(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
        )

    def record_login(self) -> None:
        """Record a successful login."""
        self.last_login_at = datetime.now(timezone.utc)
        self.failed_attempts = 0
        self.locked_until = None
        self.updated_at = datetime.now(timezone.utc)

    def record_failed_attempt(self, max_attempts: int = 5, lockout_minutes: int = 15) -> None:
        """Record a failed login attempt and lock if threshold exceeded."""
        self.failed_attempts += 1
        self.updated_at = datetime.now(timezone.utc)

        if self.failed_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc).replace(
                minute=datetime.now(timezone.utc).minute + lockout_minutes
            )

    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.now(timezone.utc) < self.locked_until


@dataclass
class RefreshToken:
    """Refresh token entity."""
    
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    is_revoked: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(user_id: UUID, token_hash: str, expires_in_days: int = 7) -> "RefreshToken":
        """Factory method to create a new RefreshToken."""
        return RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc).replace(
                day=datetime.now(timezone.utc).day + expires_in_days
            ),
        )

    def is_expired(self) -> bool:
        """Check if the refresh token has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def revoke(self) -> None:
        """Revoke this refresh token."""
        self.is_revoked = True