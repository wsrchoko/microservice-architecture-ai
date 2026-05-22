"""Auth Service - Domain Repository Interfaces."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.domain.entities import AuthUser, RefreshToken


class IAuthUserRepository(ABC):
    """Repository interface for AuthUser aggregate."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[AuthUser]:
        """Get auth user by ID."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[AuthUser]:
        """Get auth user by email."""
        pass

    @abstractmethod
    async def save(self, user: AuthUser) -> AuthUser:
        """Save or update an auth user."""
        pass

    @abstractmethod
    async def update_login(self, user_id: UUID) -> None:
        """Update last login timestamp."""
        pass

    @abstractmethod
    async def increment_failed_attempts(self, user_id: UUID) -> int:
        """Increment failed login attempts and return new count."""
        pass

    @abstractmethod
    async def lock_account(self, user_id: UUID, until: datetime) -> None:
        """Lock user account until specified time."""
        pass

    @abstractmethod
    async def unlock_account(self, user_id: UUID) -> None:
        """Unlock user account."""
        pass

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """Check if email is already registered."""
        pass


class IRefreshTokenRepository(ABC):
    """Repository interface for RefreshToken entity."""

    @abstractmethod
    async def save(self, token: RefreshToken) -> RefreshToken:
        """Save a refresh token."""
        pass

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """Get refresh token by its hash."""
        pass

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user."""
        pass

    @abstractmethod
    async def revoke_token(self, token_id: UUID) -> None:
        """Revoke a specific refresh token."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove all expired refresh tokens. Returns count removed."""
        pass