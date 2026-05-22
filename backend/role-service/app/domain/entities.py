"""Role Service - Domain Entities."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Role:
    """Role aggregate root."""
    id: UUID
    name: str
    description: Optional[str] = None
    is_system: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(name: str, description: str = None, is_system: bool = False) -> "Role":
        return Role(id=uuid4(), name=name, description=description, is_system=is_system)


@dataclass
class Permission:
    """Permission entity."""
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    resource: str = ""
    action: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserRole:
    """User role assignment value object."""
    user_id: UUID
    role_id: UUID
    assigned_by: Optional[UUID] = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))