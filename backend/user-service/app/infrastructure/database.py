"""User Service - Database models and repository implementations."""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import Column, String, Boolean, DateTime, select, func, or_
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import settings
from app.domain.entities import UserProfile
from app.domain.interfaces import IUserProfileRepository

Base = declarative_base()


class UserProfileModel(Base):
    __tablename__ = "profiles"
    __table_args__ = {"schema": "users"}
    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DatabaseSessionManager:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def get_session(self) -> AsyncSession:
        return self.session_factory()

    async def close(self) -> None:
        await self.engine.dispose()


class UserProfileRepository(IUserProfileRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, profile_id: UUID) -> Optional[UserProfile]:
        model = await self.session.get(UserProfileModel, profile_id)
        return self._to_domain(model) if model else None

    async def get_by_user_id(self, user_id: UUID) -> Optional[UserProfile]:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def save(self, profile: UserProfile) -> UserProfile:
        model = UserProfileModel(
            id=profile.id, user_id=profile.user_id, first_name=profile.first_name, last_name=profile.last_name,
            phone=profile.phone, avatar_url=profile.avatar_url, department=profile.department,
            position=profile.position, is_deleted=profile.is_deleted, created_at=profile.created_at, updated_at=profile.updated_at,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def update(self, profile: UserProfile) -> UserProfile:
        model = await self.session.get(UserProfileModel, profile.id)
        if model:
            model.first_name = profile.first_name
            model.last_name = profile.last_name
            model.phone = profile.phone
            model.department = profile.department
            model.position = profile.position
            model.updated_at = profile.updated_at
            await self.session.commit()
            await self.session.refresh(model)
        return self._to_domain(model)

    async def soft_delete(self, user_id: UUID) -> None:
        model = await self.session.get(UserProfileModel, user_id)
        if model:
            model.is_deleted = True
            await self.session.commit()

    async def search(self, query: str, skip: int = 0, limit: int = 20) -> List[UserProfile]:
        stmt = select(UserProfileModel).where(
            or_(
                UserProfileModel.first_name.ilike(f"%{query}%"),
                UserProfileModel.last_name.ilike(f"%{query}%"),
                UserProfileModel.department.ilike(f"%{query}%"),
            )
        ).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_all(self, skip: int = 0, limit: int = 20) -> List[UserProfile]:
        stmt = select(UserProfileModel).offset(skip).limit(limit).order_by(UserProfileModel.created_at.desc())
        result = await self.session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def exists_by_user_id(self, user_id: UUID) -> bool:
        stmt = select(func.count()).select_from(UserProfileModel).where(UserProfileModel.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar() > 0

    def _to_domain(self, model: UserProfileModel) -> UserProfile:
        return UserProfile(
            id=model.id, user_id=model.user_id, first_name=model.first_name, last_name=model.last_name,
            phone=model.phone, avatar_url=model.avatar_url, department=model.department,
            position=model.position, is_deleted=model.is_deleted, created_at=model.created_at, updated_at=model.updated_at,
        )