"""Role Service - Repository Interfaces."""
from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from app.domain.entities import Role, Permission, UserRole


class IRoleRepository(ABC):
    @abstractmethod
    async def get_by_id(self, role_id: UUID) -> Optional[Role]: pass
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Role]: pass
    @abstractmethod
    async def save(self, role: Role) -> Role: pass
    @abstractmethod
    async def get_all(self) -> List[Role]: pass
    @abstractmethod
    async def delete(self, role_id: UUID) -> bool: pass


class IPermissionRepository(ABC):
    @abstractmethod
    async def get_by_id(self, perm_id: UUID) -> Optional[Permission]: pass
    @abstractmethod
    async def get_by_code(self, code: str) -> Optional[Permission]: pass
    @abstractmethod
    async def get_all(self) -> List[Permission]: pass
    @abstractmethod
    async def get_by_role_id(self, role_id: UUID) -> List[Permission]: pass


class IUserRoleRepository(ABC):
    @abstractmethod
    async def assign_role(self, user_id: UUID, role_id: UUID, assigned_by: UUID = None) -> UserRole: pass
    @abstractmethod
    async def revoke_role(self, user_id: UUID, role_id: UUID) -> bool: pass
    @abstractmethod
    async def get_user_roles(self, user_id: UUID) -> List[Role]: pass
    @abstractmethod
    async def get_role_users(self, role_id: UUID) -> List[UUID]: pass