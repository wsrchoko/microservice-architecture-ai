"""Role Service - DTOs."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AssignRoleRequest(BaseModel):
    user_id: str
    role_id: str


class PermissionResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    resource: str
    action: str