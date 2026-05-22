"""Shared security utilities: JWT handling, password hashing, rate limiting."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from pydantic import BaseModel, Field

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


# ============================================
# Password Hashing
# ============================================

class PasswordUtils:
    """Utility class for password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash.

        Args:
            password: Plain text password to verify
            hashed: Stored password hash

        Returns:
            True if password matches hash
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed.encode("utf-8")
            )
        except Exception as e:
            logger.error("Password verification error", extra={"error": str(e)})
            return False


# ============================================
# JWT Token Management
# ============================================

class TokenPayload(BaseModel):
    """JWT token payload structure."""
    sub: str  # User ID
    email: str
    type: str = "access"  # access or refresh
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    exp: Optional[int] = None
    iat: Optional[int] = None
    jti: Optional[str] = None


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class JWTProvider:
    """JWT token provider for authentication."""

    def __init__(
        self,
        secret: str = settings.jwt_secret,
        algorithm: str = settings.jwt_algorithm,
        access_token_expire_minutes: int = settings.access_token_expire_minutes,
        refresh_token_expire_days: int = settings.refresh_token_expire_days,
    ):
        self.secret = secret
        self.algorithm = algorithm
        self.access_token_expire = access_token_expire_minutes
        self.refresh_token_expire = refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        email: str,
        roles: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
    ) -> str:
        """Create a JWT access token.

        Args:
            user_id: User identifier
            email: User email
            roles: List of user roles
            permissions: List of user permissions

        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id,
            email=email,
            type="access",
            roles=roles or [],
            permissions=permissions or [],
            exp=int((now + timedelta(minutes=self.access_token_expire)).timestamp()),
            iat=int(now.timestamp()),
            jti=str(uuid.uuid4()),
        )

        return jwt.encode(
            payload.model_dump(),
            self.secret,
            algorithm=self.algorithm,
        )

    def create_refresh_token(self, user_id: str, email: str) -> str:
        """Create a JWT refresh token.

        Args:
            user_id: User identifier
            email: User email

        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id,
            email=email,
            type="refresh",
            exp=int((now + timedelta(days=self.refresh_token_expire)).timestamp()),
            iat=int(now.timestamp()),
            jti=str(uuid.uuid4()),
        )

        return jwt.encode(
            payload.model_dump(),
            self.secret,
            algorithm=self.algorithm,
        )

    def create_token_pair(
        self,
        user_id: str,
        email: str,
        roles: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
    ) -> TokenPair:
        """Create both access and refresh tokens.

        Args:
            user_id: User identifier
            email: User email
            roles: List of user roles
            permissions: List of user permissions

        Returns:
            TokenPair with access and refresh tokens
        """
        return TokenPair(
            access_token=self.create_access_token(
                user_id, email, roles, permissions
            ),
            refresh_token=self.create_refresh_token(user_id, email),
            token_type="Bearer",
            expires_in=self.access_token_expire * 60,
        )

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", extra={"error": str(e)})
            return None

    def refresh_access_token(
        self,
        refresh_token: str,
        roles: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
    ) -> Optional[TokenPair]:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: Valid refresh token
            roles: Updated roles
            permissions: Updated permissions

        Returns:
            New TokenPair or None if refresh token is invalid
        """
        payload = self.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None

        return self.create_token_pair(
            user_id=payload["sub"],
            email=payload["email"],
            roles=roles,
            permissions=permissions,
        )


# ============================================
# Rate Limiting
# ============================================

class RateLimiter:
    """Simple in-memory rate limiter (for development).

    In production, replace with Redis-based implementation.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list[datetime]] = {}

    def check(self, key: str) -> bool:
        """Check if a request is allowed.

        Args:
            key: Unique key (e.g., user_id, IP address)

        Returns:
            True if request is allowed
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self.window_seconds)

        # Clean old entries
        if key in self.requests:
            self.requests[key] = [
                t for t in self.requests[key] if t > window_start
            ]
        else:
            self.requests[key] = []

        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True


# ============================================
# Input Validation & Sanitization
# ============================================

def sanitize_email(email: str) -> str:
    """Sanitize and normalize an email address.

    Args:
        email: Raw email input

    Returns:
        Sanitized email
    """
    return email.strip().lower()


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Sanitize a string input.

    Args:
        value: Raw string input
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    # Strip whitespace and truncate
    sanitized = value.strip()[:max_length]
    # Remove any null bytes
    sanitized = sanitized.replace("\x00", "")
    return sanitized


# ============================================
# Correlation ID Generator
# ============================================

def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing.

    Returns:
        Correlation ID string
    """
    return str(uuid.uuid4())


def hash_token(token: str) -> str:
    """Hash a token for secure storage.

    Args:
        token: Token to hash

    Returns:
        SHA-256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()