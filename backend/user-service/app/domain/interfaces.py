"""User Service - Repository Interfaces."""
from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from app.domain.entities import UserProfile


class IUserProfileRepository(ABC):
    @abstractmethod
    async def get_by_id(self, profile_id: UUID) -> Optional[UserProfile]: pass
    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> Optional[UserProfile]: pass
    @abstractmethod
    async def save(self, profile: UserProfile) -> UserProfile: pass
    @abstractmethod
    async def update(self, profile: UserProfile) -> UserProfile: pass
    @abstractmethod
    async def soft_delete(self, user_id: UUID) -> None: pass
    @abstractmethod
    async def search(self, query: str, skip: int = 0, limit: int = 20) -> List[UserProfile]: pass
    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 20) -> List[UserProfile]: pass
    @abstractmethod
    async def exists_by_user_id(self, user_id: UUID) -> bool: pass