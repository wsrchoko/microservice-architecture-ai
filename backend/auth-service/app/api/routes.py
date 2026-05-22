"""Auth Service - REST API Routes."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.dto import (
    SignupRequest,
    LoginRequest,
    RefreshTokenRequest,
    AuthResponse,
    TokenResponse,
    ErrorResponse,
)
from app.core.services import AuthService
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)


def get_auth_service() -> AuthService:
    """Dependency injection for AuthService - will be set by app startup."""
    from app.main import auth_service as svc
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service not initialized",
        )
    return svc


def _handle_service_error(e: Exception) -> HTTPException:
    """Handle service layer exceptions consistently."""
    logger.warning("Service error", extra={"error": str(e), "type": type(e).__name__})
    if isinstance(e, ValueError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred",
    )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account with email and password authentication",
)
async def signup(request: SignupRequest):
    """Register a new user in the system.

    Validates password strength, checks email uniqueness,
    and returns JWT tokens for immediate authentication.
    """
    try:
        svc = get_auth_service()
        result = await svc.signup(request)
        return result
    except Exception as e:
        raise _handle_service_error(e)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate user",
    description="Authenticate with email and password, returns JWT tokens",
)
async def login(request: LoginRequest):
    """Authenticate a user with email and password.

    Handles account locking after multiple failed attempts.
    Returns access token (30 min) and refresh token (7 days).
    """
    try:
        svc = get_auth_service()
        result = await svc.login(request)
        logger.info(
            "User login successful",
            extra={"email": request.email},
        )
        return result
    except Exception as e:
        raise _handle_service_error(e)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Get a new access token using a valid refresh token",
)
async def refresh(request: RefreshTokenRequest):
    """Refresh access token using a valid refresh token.

    The old refresh token is revoked and a new one is issued (token rotation).
    """
    try:
        svc = get_auth_service()
        result = await svc.refresh_token(request.refresh_token)
        return result
    except Exception as e:
        raise _handle_service_error(e)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout user",
    description="Revoke all refresh tokens for the authenticated user",
)
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Logout by revoking all refresh tokens for the current user.

    Requires a valid Bearer token in the Authorization header.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        svc = get_auth_service()
        payload = await svc.validate_token(credentials.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        await svc.logout(UUID(payload["sub"]))
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_service_error(e)


@router.get(
    "/validate",
    summary="Validate access token",
    description="Check if an access token is valid and return its payload",
)
async def validate_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Validate the current access token.

    Returns the token payload including user ID, email, roles, and permissions.
    Used by other services to verify authentication.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    svc = get_auth_service()
    payload = await svc.validate_token(credentials.credentials)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return payload


@router.get(
    "/health",
    summary="Health check",
    description="Service health check endpoint",
)
async def health():
    """Health check endpoint for Docker container orchestration."""
    return {
        "status": "healthy",
        "service": "auth-service",
        "version": "1.0.0",
    }