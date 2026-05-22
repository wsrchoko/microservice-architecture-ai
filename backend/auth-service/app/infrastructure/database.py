"""Auth Service - Database models and repository implementations."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship

from app.config import settings
from app.domain.entities import AuthUser, RefreshToken
from app.domain.interfaces import IAuthUserRepository, IRefreshTokenRepository
from app.logging import get_logger

logger = get_logger(__name__)

Base = declarative_base()


# ============================================
# SQLAlchemy ORM Models
# ============================================

class AuthUserModel(Base):
    """Auth user ORM model - maps to auth.users table."""
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RefreshTokenModel(Base):
    """Refresh token ORM model - maps to auth.refresh_tokens table."""
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "auth"}

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("auth.users.id"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ============================================
# Database Session Manager
# ============================================

class DatabaseSessionManager:
    """Manages async database sessions."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self) -> None:
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """Get a new database session."""
        return self.session_factory()

    async def close(self) -> None:
        """Close the database engine."""
        await self.engine.dispose()


# ============================================
# Repository Implementations
# ============================================

class AuthUserRepository(IAuthUserRepository):
    """PostgreSQL implementation of IAuthUserRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> Optional[AuthUser]:
        result = await self.session.get(AuthUserModel, user_id)
        return self._to_domain(result) if result else None

    async def get_by_email(self, email: str) -> Optional[AuthUser]:
        from sqlalchemy import select
        stmt = select(AuthUserModel).where(AuthUserModel.email == email)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def save(self, user: AuthUser) -> AuthUser:
        model = AuthUserModel(
            id=user.id,
            email=user.email,
            password_hash=user.password_hash,
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login_at=user.last_login_at,
            failed_attempts=user.failed_attempts,
            locked_until=user.locked_until,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def update_login(self, user_id: UUID) -> None:
        model = await self.session.get(AuthUserModel, user_id)
        if model:
            model.last_login_at = datetime.now(timezone.utc)
            model.failed_attempts = 0
            model.locked_until = None
            await self.session.commit()

    async def increment_failed_attempts(self, user_id: UUID) -> int:
        model = await self.session.get(AuthUserModel, user_id)
        if model:
            model.failed_attempts = (model.failed_attempts or 0) + 1
            await self.session.commit()
            return model.failed_attempts
        return 0

    async def lock_account(self, user_id: UUID, until: datetime) -> None:
        model = await self.session.get(AuthUserModel, user_id)
        if model:
            model.locked_until = until
            await self.session.commit()

    async def unlock_account(self, user_id: UUID) -> None:
        model = await self.session.get(AuthUserModel, user_id)
        if model:
            model.locked_until = None
            model.failed_attempts = 0
            await self.session.commit()

    async def exists_by_email(self, email: str) -> bool:
        from sqlalchemy import select, exists
        stmt = select(exists().where(AuthUserModel.email == email))
        result = await self.session.execute(stmt)
        return result.scalar() or False

    def _to_domain(self, model: AuthUserModel) -> AuthUser:
        return AuthUser(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            is_active=model.is_active,
            is_verified=model.is_verified,
            last_login_at=model.last_login_at,
            failed_attempts=model.failed_attempts,
            locked_until=model.locked_until,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class RefreshTokenRepository(IRefreshTokenRepository):
    """PostgreSQL implementation of IRefreshTokenRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, token: RefreshToken) -> RefreshToken:
        model = RefreshTokenModel(
            id=token.id,
            user_id=token.user_id,
            token_hash=token.token_hash,
            expires_at=token.expires_at,
            is_revoked=token.is_revoked,
            created_at=token.created_at,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def get_by_token_hash(self, token_hash: str) -> Optional[RefreshToken]:
        from sqlalchemy import select
        stmt = select(RefreshTokenModel).where(
            RefreshTokenModel.token_hash == token_hash
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        from sqlalchemy import update
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def revoke_token(self, token_id: UUID) -> None:
        model = await self.session.get(RefreshTokenModel, token_id)
        if model:
            model.is_revoked = True
            await self.session.commit()

    async def cleanup_expired(self) -> int:
        from sqlalchemy import delete
        stmt = delete(RefreshTokenModel).where(
            RefreshTokenModel.expires_at < datetime.now(timezone.utc)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    def _to_domain(self, model: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            is_revoked=model.is_revoked,
            created_at=model.created_at,
        )