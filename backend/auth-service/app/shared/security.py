"""Security utilities for Auth Service."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from pydantic import BaseModel, Field

from app.config import settings


class PasswordUtils:
    """Utility class for password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False


class TokenPayload(BaseModel):
    sub: str
    email: str
    type: str = "access"
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    exp: Optional[int] = None
    iat: Optional[int] = None
    jti: Optional[str] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class JWTProvider:
    def __init__(self):
        self.secret = settings.jwt_secret
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire = settings.access_token_expire_minutes
        self.refresh_token_expire = settings.refresh_token_expire_days

    def create_access_token(self, user_id: str, email: str, roles: list[str] = None, permissions: list[str] = None) -> str:
        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id, email=email, type="access",
            roles=roles or [], permissions=permissions or [],
            exp=int((now + timedelta(minutes=self.access_token_expire)).timestamp()),
            iat=int(now.timestamp()), jti=str(uuid.uuid4()),
        )
        return jwt.encode(payload.model_dump(), self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str, email: str) -> str:
        now = datetime.now(timezone.utc)
        payload = TokenPayload(
            sub=user_id, email=email, type="refresh",
            exp=int((now + timedelta(days=self.refresh_token_expire)).timestamp()),
            iat=int(now.timestamp()), jti=str(uuid.uuid4()),
        )
        return jwt.encode(payload.model_dump(), self.secret, algorithm=self.algorithm)

    def create_token_pair(self, user_id: str, email: str, roles: list[str] = None, permissions: list[str] = None) -> TokenPair:
        return TokenPair(
            access_token=self.create_access_token(user_id, email, roles, permissions),
            refresh_token=self.create_refresh_token(user_id, email),
            token_type="Bearer", expires_in=self.access_token_expire * 60,
        )

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.algorithm], options={"verify_exp": True})
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sanitize_email(email: str) -> str:
    return email.strip().lower()


def sanitize_string(value: str, max_length: int = 255) -> str:
    sanitized = value.strip()[:max_length]
    return sanitized.replace("\x00", "")