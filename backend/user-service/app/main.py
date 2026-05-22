"""User Service - FastAPI Application Entry Point."""
import sys, os
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging import setup_logging, get_logger
from app.api.routes import router
from app.infrastructure.database import DatabaseSessionManager, UserProfileRepository
from app.core.services import UserService

user_service: Optional[UserService] = None
db_manager: Optional[DatabaseSessionManager] = None
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global user_service, db_manager
    setup_logging(service_name=settings.service_name, log_level=settings.log_level)
    logger.info("Starting User Service")
    db_manager = DatabaseSessionManager(settings.database_url)
    session = await db_manager.get_session()
    repo = UserProfileRepository(session)
    user_service = UserService(repo)
    logger.info("User Service started successfully")
    yield
    logger.info("Shutting down User Service")
    if db_manager:
        await db_manager.close()


app = FastAPI(title="Nexus User Service", description="User Profile Microservice", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", extra={"path": request.url.path, "error": str(exc)})
    return JSONResponse(status_code=500, content={"detail": "An internal server error occurred"})


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)