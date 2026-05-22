"""Role Service - Application Services."""
from uuid import UUID
from typing import Optional, List
from app.domain.entities import Role, Permission, UserRole
from app.domain.interfaces import IRoleRepository, IPermissionRepository, IUserRoleRepository
from app.core.dto import CreateRoleRequest, RoleResponse
from app.logging import get_logger

logger = get_logger(__name__)


class RoleService:
    def __init__(self, role_repo: IRoleRepository, perm_repo: IPermissionRepository, user_role_repo: IUserRoleRepository):
        self.role_repo = role_repo
        self.perm_repo = perm_repo
        self.user_role_repo = user_role_repo

    async def create_role(self, request: CreateRoleRequest) -> RoleResponse:
        existing = await self.role_repo.get_by_name(request.name)
        if existing:
            raise ValueError(f"Role '{request.name}' already exists")
        role = Role.create(name=request.name, description=request.description)
        saved = await self.role_repo.save(role)
        logger.info("Role created", extra={"role": request.name})
        return self._to_response(saved, [])

    async def get_all_roles(self) -> List[RoleResponse]:
        roles = await self.role_repo.get_all()
        result = []
        for role in roles:
            perms = await self.perm_repo.get_by_role_id(role.id)
            result.append(self._to_response(role, perms))
        return result

    async def get_role(self, role_id: UUID) -> Optional[RoleResponse]:
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            return None
        perms = await self.perm_repo.get_by_role_id(role.id)
        return self._to_response(role, perms)

    async def assign_role_to_user(self, user_id: UUID, role_id: UUID, assigned_by: UUID = None):
        user_role = await self.user_role_repo.assign_role(user_id, role_id, assigned_by)
        logger.info("Role assigned", extra={"user_id": str(user_id), "role_id": str(role_id)})
        return user_role

    async def revoke_role_from_user(self, user_id: UUID, role_id: UUID) -> bool:
        result = await self.user_role_repo.revoke_role(user_id, role_id)
        if result:
            logger.info("Role revoked", extra={"user_id": str(user_id), "role_id": str(role_id)})
        return result

    async def get_user_permissions(self, user_id: UUID) -> List[str]:
        roles = await self.user_role_repo.get_user_roles(user_id)
        permissions = []
        for role in roles:
            perms = await self.perm_repo.get_by_role_id(role.id)
            permissions.extend([p.code for p in perms])
        return list(set(permissions))

    def _to_response(self, role: Role, permissions: List[Permission]) -> RoleResponse:
        return RoleResponse(
            id=str(role.id), name=role.name, description=role.description,
            is_system=role.is_system,
            permissions=[p.code for p in permissions],
            created_at=role.created_at, updated_at=role.updated_at,
        )