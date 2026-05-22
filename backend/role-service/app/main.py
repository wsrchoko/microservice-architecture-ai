"""Role Service - FastAPI Application."""
import sys, os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.logging import setup_logging, get_logger
from app.api.routes import router
from app.infrastructure.database import DatabaseSessionManager, RoleRepository, PermissionRepository, UserRoleRepository
from app.core.services import RoleService

role_service: Optional[RoleService] = None
db_manager: Optional[DatabaseSessionManager] = None
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global role_service, db_manager
    setup_logging(service_name=settings.service_name, log_level=settings.log_level)
    logger.info("Starting Role Service")
    db_manager = DatabaseSessionManager(settings.database_url)
    session = await db_manager.get_session()
    role_repo = RoleRepository(session)
    perm_repo = PermissionRepository(session)
    user_role_repo = UserRoleRepository(session)
    role_service = RoleService(role_repo, perm_repo, user_role_repo)
    logger.info("Role Service started successfully")
    yield
    if db_manager: await db_manager.close()


app = FastAPI(title="Nexus Role Service", description="Role & Permission Microservice", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", extra={"path": request.url.path, "error": str(exc)})
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred"})


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8003, reload=True)