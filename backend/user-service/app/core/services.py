"""User Service - Application Services."""
from uuid import UUID
from typing import Optional, List
from app.domain.entities import UserProfile
from app.domain.interfaces import IUserProfileRepository
from app.core.dto import CreateProfileRequest, UpdateProfileRequest, ProfileResponse
from app.logging import get_logger

logger = get_logger(__name__)


class UserService:
    def __init__(self, repo: IUserProfileRepository):
        self.repo = repo

    async def create_profile(self, user_id: UUID, request: CreateProfileRequest) -> ProfileResponse:
        profile = UserProfile.create(user_id=user_id, first_name=request.first_name, last_name=request.last_name)
        profile.phone = request.phone
        profile.department = request.department
        profile.position = request.position
        saved = await self.repo.save(profile)
        logger.info("Profile created", extra={"user_id": str(user_id)})
        return self._to_response(saved)

    async def get_profile(self, user_id: UUID) -> Optional[ProfileResponse]:
        profile = await self.repo.get_by_user_id(user_id)
        if not profile or profile.is_deleted:
            return None
        return self._to_response(profile)

    async def update_profile(self, user_id: UUID, request: UpdateProfileRequest) -> Optional[ProfileResponse]:
        profile = await self.repo.get_by_user_id(user_id)
        if not profile or profile.is_deleted:
            return None
        profile.update(
            first_name=request.first_name, last_name=request.last_name,
            phone=request.phone, department=request.department, position=request.position,
        )
        updated = await self.repo.update(profile)
        logger.info("Profile updated", extra={"user_id": str(user_id)})
        return self._to_response(updated)

    async def delete_profile(self, user_id: UUID) -> bool:
        profile = await self.repo.get_by_user_id(user_id)
        if not profile:
            return False
        await self.repo.soft_delete(user_id)
        logger.info("Profile soft deleted", extra={"user_id": str(user_id)})
        return True

    async def list_profiles(self, skip: int = 0, limit: int = 20) -> tuple[List[ProfileResponse], int]:
        profiles = await self.repo.get_all(skip=skip, limit=limit)
        return [self._to_response(p) for p in profiles if not p.is_deleted], len(profiles)

    async def search_profiles(self, query: str, skip: int = 0, limit: int = 20) -> list[ProfileResponse]:
        profiles = await self.repo.search(query, skip=skip, limit=limit)
        return [self._to_response(p) for p in profiles if not p.is_deleted]

    def _to_response(self, profile: UserProfile) -> ProfileResponse:
        return ProfileResponse(
            id=str(profile.id), user_id=str(profile.user_id),
            first_name=profile.first_name, last_name=profile.last_name,
            phone=profile.phone, avatar_url=profile.avatar_url,
            department=profile.department, position=profile.position,
            is_deleted=profile.is_deleted, created_at=profile.created_at, updated_at=profile.updated_at,
        )