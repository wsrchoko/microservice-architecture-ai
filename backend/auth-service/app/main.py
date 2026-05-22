"""Auth Service - FastAPI Application Entry Point."""

import sys
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging import setup_logging, get_logger
from app.api.routes import router
from app.infrastructure.database import DatabaseSessionManager, AuthUserRepository, RefreshTokenRepository
from app.core.services import AuthService
from app.shared.messaging import EventBus, EventTopics, EventExchanges

# Will be set at startup
auth_service: Optional[AuthService] = None
event_bus: Optional[EventBus] = None
db_manager: Optional[DatabaseSessionManager] = None

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - handles startup and shutdown."""
    global auth_service, event_bus, db_manager

    # Setup logging
    setup_logging(
        service_name=settings.service_name,
        log_level=settings.log_level,
    )
    logger.info("Starting Auth Service")

    # Initialize database
    db_manager = DatabaseSessionManager(settings.database_url)
    
    # Get session and create repositories
    session = await db_manager.get_session()
    user_repo = AuthUserRepository(session)
    refresh_token_repo = RefreshTokenRepository(session)

    # Initialize auth service
    auth_service = AuthService(
        user_repo=user_repo,
        refresh_token_repo=refresh_token_repo,
    )

    # Initialize event bus
    event_bus = EventBus(
        rabbitmq_url=settings.rabbitmq_url,
        service_name=settings.service_name,
    )
    try:
        await event_bus.connect()
        await event_bus.declare_exchange(EventExchanges.AUTH_EVENTS)
        logger.info("Connected to message broker")
    except Exception as e:
        logger.warning(
            "Failed to connect to message broker - continuing without events",
            extra={"error": str(e)},
        )

    logger.info("Auth Service started successfully")
    yield

    # Shutdown
    logger.info("Shutting down Auth Service")
    if event_bus:
        await event_bus.close()
    if db_manager:
        await db_manager.close()


app = FastAPI(
    title="Nexus Auth Service",
    description="Authentication and Authorization Microservice",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred",
            "error_code": "INTERNAL_ERROR",
        },
    )


# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )