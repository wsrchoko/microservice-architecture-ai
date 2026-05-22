"""User Service - Domain Entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class UserProfile:
    """User profile aggregate root."""
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_deleted: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(user_id: UUID, first_name: str, last_name: str) -> "UserProfile":
        return UserProfile(id=uuid4(), user_id=user_id, first_name=first_name, last_name=last_name)

    def update(self, first_name: str = None, last_name: str = None, phone: str = None,
               department: str = None, position: str = None) -> None:
        if first_name: self.first_name = first_name
        if last_name: self.last_name = last_name
        if phone is not None: self.phone = phone
        if department is not None: self.department = department
        if position is not None: self.position = position
        self.updated_at = datetime.now(timezone.utc)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.updated_at = datetime.now(timezone.utc)