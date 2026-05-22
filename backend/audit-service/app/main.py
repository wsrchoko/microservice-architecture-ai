"""Audit Service - FastAPI Application with MongoDB."""
import json, os, sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Request, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from motor.motor_asyncio import AsyncIOMotorClient
import logging


class Settings(BaseSettings):
    service_name: str = "audit-service"
    service_version: str = "1.0.0"
    log_level: str = "INFO"
    mongodb_url: str = "mongodb://nexus_user:nexus_secure_password_2025@localhost:27017/nexus_audit?authSource=admin"
    rabbitmq_url: str = "amqp://nexus_user:nexus_rabbit_password@localhost:5672/"
    class Config: env_file = ".env"; extra = "ignore"

settings = Settings()

# Setup logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(settings.service_name)

# MongoDB connection
client: Optional[AsyncIOMotorClient] = None
db = None


class AuditLogEntry(BaseModel):
    event_type: str
    source: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    action: str
    resource: str
    details: dict = Field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    correlation_id: Optional[str] = None
    success: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLogResponse(BaseModel):
    id: str
    event_type: str
    source: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    action: str
    resource: str
    details: dict
    ip_address: Optional[str] = None
    success: bool
    timestamp: datetime


class AuditLogList(BaseModel):
    items: list[AuditLogResponse]
    total: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db
    logger.info("Starting Audit Service")
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client.nexus_audit
    # Create indexes
    await db.audit_logs.create_index("event_type")
    await db.audit_logs.create_index("user_id")
    await db.audit_logs.create_index("timestamp")
    await db.audit_logs.create_index([("timestamp", -1)])
    logger.info("Audit Service started")
    yield
    if client: client.close()
    logger.info("Audit Service stopped")


app = FastAPI(title="Nexus Audit Service", description="Audit Logging Microservice", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.post("/api/v1/audit/logs", status_code=status.HTTP_201_CREATED)
async def create_audit_log(entry: AuditLogEntry):
    doc = entry.model_dump()
    result = await db.audit_logs.insert_one(doc)
    return {"id": str(result.inserted_id)}


@app.get("/api/v1/audit/logs", response_model=AuditLogList)
async def list_audit_logs(
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    source: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    query = {}
    if event_type: query["event_type"] = event_type
    if user_id: query["user_id"] = user_id
    if source: query["source"] = source
    
    cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.audit_logs.count_documents(query)
    
    return AuditLogList(
        items=[AuditLogResponse(id=str(item["_id"]), **{k: v for k, v in item.items() if k != "_id"}) for item in items],
        total=total,
    )


@app.get("/api/v1/audit/logs/{log_id}")
async def get_audit_log(log_id: str):
    from bson.objectid import ObjectId
    item = await db.audit_logs.find_one({"_id": ObjectId(log_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Log not found")
    return AuditLogResponse(id=str(item["_id"]), **{k: v for k, v in item.items() if k != "_id"})


@app.get("/api/v1/audit/stats")
async def get_audit_stats():
    pipeline = [
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    cursor = db.audit_logs.aggregate(pipeline)
    stats = await cursor.to_list(length=100)
    return {"stats": [{"event_type": s["_id"], "count": s["count"]} for s in stats]}


@app.get("/api/v1/audit/health")
async def health():
    return {"status": "healthy", "service": "audit-service", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)