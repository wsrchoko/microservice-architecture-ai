"""User Service - REST API Routes."""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.dto import CreateProfileRequest, UpdateProfileRequest, ProfileResponse, UserListResponse
from app.core.services import UserService
from app.logging import get_logger
import httpx

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["Users"])
security = HTTPBearer(auto_error=False)

AUTH_SERVICE_URL = "http://auth-service:8001"


def get_user_service() -> UserService:
    from app.main import user_service as svc
    if svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service not initialized")
    return svc


async def validate_token(token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{AUTH_SERVICE_URL}/api/v1/auth/validate",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return resp.json()


@router.post("/{user_id}/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(user_id: UUID, request: CreateProfileRequest):
    try:
        svc = get_user_service()
        return await svc.create_profile(user_id, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{user_id}/profile", response_model=ProfileResponse)
async def get_profile(user_id: UUID):
    svc = get_user_service()
    profile = await svc.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.put("/{user_id}/profile", response_model=ProfileResponse)
async def update_profile(user_id: UUID, request: UpdateProfileRequest):
    svc = get_user_service()
    profile = await svc.update_profile(user_id, request)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.delete("/{user_id}/profile", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(user_id: UUID):
    svc = get_user_service()
    deleted = await svc.delete_profile(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")


@router.get("", response_model=UserListResponse)
async def list_profiles(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    svc = get_user_service()
    items, total = await svc.list_profiles(skip=skip, limit=limit)
    return UserListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/search", response_model=list[ProfileResponse])
async def search_profiles(q: str = Query(..., min_length=1), skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    svc = get_user_service()
    return await svc.search_profiles(q, skip=skip, limit=limit)


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "user-service", "version": "1.0.0"}