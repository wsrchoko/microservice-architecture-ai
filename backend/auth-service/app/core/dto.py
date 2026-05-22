"""Auth Service - Data Transfer Objects."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.shared.security import sanitize_email, sanitize_string


# ============================================
# Request DTOs
# ============================================

class SignupRequest(BaseModel):
    """User signup request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("email")
    @classmethod
    def sanitize_email_input(cls, v: str) -> str:
        """Sanitize email input."""
        return sanitize_email(v)

    @field_validator("first_name", "last_name")
    @classmethod
    def sanitize_name_input(cls, v: str) -> str:
        """Sanitize name inputs."""
        return sanitize_string(v, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def sanitize_email_input(cls, v: str) -> str:
        """Sanitize email input."""
        return sanitize_email(v)


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., min_length=1)


# ============================================
# Response DTOs
# ============================================

class TokenResponse(BaseModel):
    """Authentication token response."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User data response."""
    id: str
    email: str
    is_active: bool
    is_verified: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AuthResponse(BaseModel):
    """Complete authentication response."""
    user: UserResponse
    tokens: TokenResponse


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: str = "UNKNOWN_ERROR"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorResponse(BaseModel):
    """Validation error with field details."""
    detail: str
    errors: list[dict] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)