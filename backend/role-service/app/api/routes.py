"""Role Service - REST API Routes."""
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from app.core.dto import CreateRoleRequest, RoleResponse, AssignRoleRequest, PermissionResponse
from app.core.services import RoleService
from app.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/roles", tags=["Roles"])


def get_role_service() -> RoleService:
    from app.main import role_service as svc
    if svc is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service not initialized")
    return svc


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(request: CreateRoleRequest):
    try:
        svc = get_role_service()
        return await svc.create_role(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[RoleResponse])
async def list_roles():
    svc = get_role_service()
    return await svc.get_all_roles()


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "role-service", "version": "1.0.0"}


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(role_id: UUID):
    svc = get_role_service()
    role = await svc.get_role(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.post("/assign", status_code=status.HTTP_200_OK)
async def assign_role(request: AssignRoleRequest):
    svc = get_role_service()
    await svc.assign_role_to_user(UUID(request.user_id), UUID(request.role_id))
    return {"message": "Role assigned successfully"}


@router.delete("/{role_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_role(role_id: UUID, user_id: UUID):
    svc = get_role_service()
    await svc.revoke_role_from_user(user_id, role_id)


@router.get("/users/{user_id}/permissions", response_model=list[str])
async def get_user_permissions(user_id: UUID):
    svc = get_role_service()
    return await svc.get_user_permissions(user_id)
