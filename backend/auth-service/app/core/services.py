"""Auth Service - Application Services (Use Cases)."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from app.domain.entities import AuthUser, RefreshToken
from app.domain.interfaces import IAuthUserRepository, IRefreshTokenRepository
from app.core.dto import (
    SignupRequest,
    LoginRequest,
    AuthResponse,
    TokenResponse,
    UserResponse,
)
from app.shared.security import (
    PasswordUtils,
    JWTProvider,
    hash_token,
)

from app.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    """Authentication application service - handles use cases."""

    def __init__(
        self,
        user_repo: IAuthUserRepository,
        refresh_token_repo: IRefreshTokenRepository,
        jwt_provider: Optional[JWTProvider] = None,
    ):
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo
        self.jwt_provider = jwt_provider or JWTProvider()

    async def signup(self, request: SignupRequest) -> AuthResponse:
        """Register a new user.

        Args:
            request: Signup request with email, password, and name

        Returns:
            AuthResponse with user data and tokens

        Raises:
            ValueError: If email already exists
        """
        # Check if user already exists
        existing = await self.user_repo.exists_by_email(request.email)
        if existing:
            logger.warning("Signup attempted with existing email", extra={"email": request.email})
            raise ValueError("Email already registered")

        # Hash password
        password_hash = PasswordUtils.hash_password(request.password)

        # Create domain entity
        user = AuthUser.create(
            email=request.email,
            password_hash=password_hash,
        )

        # Persist
        saved_user = await self.user_repo.save(user)

        # Generate tokens
        tokens = self.jwt_provider.create_token_pair(
            user_id=str(saved_user.id),
            email=saved_user.email,
        )

        # Save refresh token
        refresh_token = RefreshToken.create(
            user_id=saved_user.id,
            token_hash=hash_token(tokens.refresh_token),
        )
        await self.refresh_token_repo.save(refresh_token)

        logger.info(
            "User registered successfully",
            extra={"user_id": str(saved_user.id), "email": saved_user.email},
        )

        return AuthResponse(
            user=self._map_user_to_response(saved_user),
            tokens=TokenResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            ),
        )

    async def login(self, request: LoginRequest) -> AuthResponse:
        """Authenticate a user.

        Args:
            request: Login request with email and password

        Returns:
            AuthResponse with user data and tokens

        Raises:
            ValueError: If credentials are invalid or account is locked
        """
        # Get user
        user = await self.user_repo.get_by_email(request.email)
        if not user:
            logger.warning("Login attempt for non-existent email", extra={"email": request.email})
            raise ValueError("Invalid email or password")

        # Check if account is locked
        if user.is_locked():
            logger.warning(
                "Login attempt on locked account",
                extra={"user_id": str(user.id), "locked_until": str(user.locked_until)},
            )
            raise ValueError("Account is temporarily locked. Please try again later.")

        # Verify password
        if not PasswordUtils.verify_password(request.password, user.password_hash):
            await self.user_repo.increment_failed_attempts(user.id)
            logger.warning(
                "Failed login attempt",
                extra={"user_id": str(user.id), "failed_attempts": user.failed_attempts + 1},
            )
            raise ValueError("Invalid email or password")

        # Record successful login
        user.record_login()
        await self.user_repo.update_login(user.id)

        # Get user roles and permissions from DB (simplified - in production call Role Service)
        roles: list[str] = []
        permissions: list[str] = []

        # Generate tokens
        tokens = self.jwt_provider.create_token_pair(
            user_id=str(user.id),
            email=user.email,
            roles=roles,
            permissions=permissions,
        )

        # Save refresh token
        refresh_token = RefreshToken.create(
            user_id=user.id,
            token_hash=hash_token(tokens.refresh_token),
        )
        await self.refresh_token_repo.save(refresh_token)

        logger.info(
            "User logged in successfully",
            extra={"user_id": str(user.id), "email": user.email},
        )

        return AuthResponse(
            user=self._map_user_to_response(user),
            tokens=TokenResponse(
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                token_type=tokens.token_type,
                expires_in=tokens.expires_in,
            ),
        )

    async def refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token_str: The refresh token string

        Returns:
            New TokenResponse

        Raises:
            ValueError: If refresh token is invalid
        """
        token_hash_value = hash_token(refresh_token_str)
        stored_token = await self.refresh_token_repo.get_by_token_hash(token_hash_value)

        if not stored_token:
            raise ValueError("Invalid refresh token")

        if stored_token.is_expired() or stored_token.is_revoked:
            raise ValueError("Refresh token has expired or been revoked")

        # Get user for updated roles/permissions
        user = await self.user_repo.get_by_id(stored_token.user_id)
        if not user or not user.is_active:
            raise ValueError("User account is inactive")

        # Generate new tokens
        roles: list[str] = []
        permissions: list[str] = []
        new_tokens = self.jwt_provider.create_token_pair(
            user_id=str(user.id),
            email=user.email,
            roles=roles,
            permissions=permissions,
        )

        # Revoke old refresh token
        stored_token.revoke()
        await self.refresh_token_repo.save(stored_token)

        # Save new refresh token
        new_refresh = RefreshToken.create(
            user_id=user.id,
            token_hash=hash_token(new_tokens.refresh_token),
        )
        await self.refresh_token_repo.save(new_refresh)

        return TokenResponse(
            access_token=new_tokens.access_token,
            refresh_token=new_tokens.refresh_token,
            token_type=new_tokens.token_type,
            expires_in=new_tokens.expires_in,
        )

    async def validate_token(self, token: str) -> Optional[dict]:
        """Validate an access token and return payload.

        Args:
            token: JWT access token

        Returns:
            Token payload dict or None if invalid
        """
        return self.jwt_provider.decode_token(token)

    async def logout(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user.

        Args:
            user_id: User ID to logout
        """
        await self.refresh_token_repo.revoke_all_for_user(user_id)
        logger.info("User logged out", extra={"user_id": str(user_id)})

    def _map_user_to_response(self, user: AuthUser) -> UserResponse:
        """Map AuthUser domain entity to UserResponse DTO."""
        return UserResponse(
            id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )