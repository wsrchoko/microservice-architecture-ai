"""Role Service - Database models and repositories."""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, select, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from app.config import settings
from app.domain.entities import Role, Permission, UserRole
from app.domain.interfaces import IRoleRepository, IPermissionRepository, IUserRoleRepository

Base = declarative_base()

role_permissions_table = Table(
    "role_permissions", Base.metadata,
    Column("role_id", PG_UUID(as_uuid=True), ForeignKey("roles.roles.id"), primary_key=True),
    Column("permission_id", PG_UUID(as_uuid=True), ForeignKey("roles.permissions.id"), primary_key=True),
    schema="roles",
)

user_roles_table = Table(
    "user_roles", Base.metadata,
    Column("user_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("role_id", PG_UUID(as_uuid=True), ForeignKey("roles.roles.id"), primary_key=True),
    Column("assigned_by", PG_UUID(as_uuid=True), nullable=True),
    Column("assigned_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    schema="roles",
)


class RoleModel(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "roles"}
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(500))
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PermissionModel(Base):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "roles"}
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(String(500))
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DatabaseSessionManager:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def get_session(self) -> AsyncSession: return self.session_factory()
    async def close(self) -> None: await self.engine.dispose()


class RoleRepository(IRoleRepository):
    def __init__(self, session: AsyncSession): self.session = session

    async def get_by_id(self, role_id: UUID) -> Optional[Role]:
        model = await self.session.get(RoleModel, role_id)
        return self._to_domain(model) if model else None

    async def get_by_name(self, name: str) -> Optional[Role]:
        stmt = select(RoleModel).where(RoleModel.name == name)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def save(self, role: Role) -> Role:
        model = RoleModel(id=role.id, name=role.name, description=role.description, is_system=role.is_system)
        self.session.add(model); await self.session.commit(); await self.session.refresh(model)
        return self._to_domain(model)

    async def get_all(self) -> List[Role]:
        stmt = select(RoleModel).order_by(RoleModel.name)
        result = await self.session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def delete(self, role_id: UUID) -> bool:
        model = await self.session.get(RoleModel, role_id)
        if not model or model.is_system: return False
        await self.session.delete(model); await self.session.commit(); return True

    def _to_domain(self, m: RoleModel) -> Role:
        return Role(id=m.id, name=m.name, description=m.description, is_system=m.is_system, created_at=m.created_at, updated_at=m.updated_at)


class PermissionRepository(IPermissionRepository):
    def __init__(self, session: AsyncSession): self.session = session

    async def get_by_id(self, perm_id: UUID) -> Optional[Permission]:
        model = await self.session.get(PermissionModel, perm_id)
        return self._to_domain(model) if model else None

    async def get_by_code(self, code: str) -> Optional[Permission]:
        stmt = select(PermissionModel).where(PermissionModel.code == code)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all(self) -> List[Permission]:
        stmt = select(PermissionModel).order_by(PermissionModel.name)
        result = await self.session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_by_role_id(self, role_id: UUID) -> List[Permission]:
        stmt = select(PermissionModel).join(role_permissions_table).where(role_permissions_table.c.role_id == role_id)
        result = await self.session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    def _to_domain(self, m: PermissionModel) -> Permission:
        return Permission(id=m.id, code=m.code, name=m.name, description=m.description, resource=m.resource, action=m.action, created_at=m.created_at)


class UserRoleRepository(IUserRoleRepository):
    def __init__(self, session: AsyncSession): self.session = session

    async def assign_role(self, user_id: UUID, role_id: UUID, assigned_by: UUID = None) -> UserRole:
        stmt = user_roles_table.insert().values(user_id=user_id, role_id=role_id, assigned_by=assigned_by)
        await self.session.execute(stmt); await self.session.commit()
        return UserRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by)

    async def revoke_role(self, user_id: UUID, role_id: UUID) -> bool:
        stmt = user_roles_table.delete().where(
            user_roles_table.c.user_id == user_id, user_roles_table.c.role_id == role_id
        )
        result = await self.session.execute(stmt); await self.session.commit()
        return result.rowcount > 0

    async def get_user_roles(self, user_id: UUID) -> List[Role]:
        stmt = select(RoleModel).join(user_roles_table).where(user_roles_table.c.user_id == user_id)
        result = await self.session.execute(stmt)
        return [Role(id=m.id, name=m.name, description=m.description, is_system=m.is_system, created_at=m.created_at, updated_at=m.updated_at) for m in result.scalars().all()]

    async def get_role_users(self, role_id: UUID) -> List[UUID]:
        stmt = select(user_roles_table.c.user_id).where(user_roles_table.c.role_id == role_id)
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]