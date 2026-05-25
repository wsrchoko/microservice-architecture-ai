"""System Tools - Function calling tools for the AI Agent.

Each tool wraps an API call to another microservice or system operation.
Tools are defined using LangChain's @tool decorator for automatic schema generation.
"""
import json
import httpx
from typing import Optional, List, Dict, Any
from langchain_core.tools import tool
from datetime import datetime


# Base URLs for internal microservice communication
AUTH_SERVICE_URL = "http://localhost:8001"
USER_SERVICE_URL = "http://localhost:8002"
ROLE_SERVICE_URL = "http://localhost:8003"
AUDIT_SERVICE_URL = "http://localhost:8004"
AI_SERVICE_URL = "http://localhost:8005"

TIMEOUT = 15.0  # seconds


async def _get_json(url: str, params: Optional[dict] = None) -> dict:
    """Async GET request returning JSON."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def _post_json(url: str, payload: dict) -> dict:
    """Async POST request returning JSON."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


# ─────────────────────────────────────────────────────────
# USER SERVICE TOOLS
# ─────────────────────────────────────────────────────────

@tool
async def get_user_profile(user_id: str) -> dict:
    """Get a user's profile by their user ID.
    
    Args:
        user_id: The unique identifier of the user (UUID string).
    
    Returns:
        User profile data including name, email, department, bio, etc.
    """
    try:
        data = await _get_json(f"{USER_SERVICE_URL}/api/v1/users/{user_id}/profile")
        return {"success": True, "user_id": user_id, "profile": data}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"User not found: {e.response.status_code}", "user_id": user_id}
    except Exception as e:
        return {"success": False, "error": str(e), "user_id": user_id}


@tool
async def list_users(skip: int = 0, limit: int = 20) -> dict:
    """List all user profiles in the system.
    
    Args:
        skip: Number of records to skip (pagination).
        limit: Maximum number of records to return (max 100).
    
    Returns:
        List of user profiles.
    """
    try:
        data = await _get_json(f"{USER_SERVICE_URL}/api/v1/users", params={"skip": skip, "limit": min(limit, 100)})
        return {"success": True, "users": data.get("items", data), "total": data.get("total", len(data))}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
async def search_users(query: str) -> dict:
    """Search for users by name or department.
    
    Args:
        query: Search term to match against user names or departments.
    
    Returns:
        Matching user profiles.
    """
    try:
        data = await _get_json(f"{USER_SERVICE_URL}/api/v1/users/search", params={"query": query})
        return {"success": True, "query": query, "results": data.get("items", data), "count": len(data.get("items", data if isinstance(data, list) else []))}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────
# ROLE SERVICE TOOLS
# ─────────────────────────────────────────────────────────

@tool
async def list_roles() -> dict:
    """List all roles and their associated permissions in the system.
    
    Returns:
        List of roles with their permissions.
    """
    try:
        data = await _get_json(f"{ROLE_SERVICE_URL}/api/v1/roles")
        return {"success": True, "roles": data.get("items", data), "count": len(data.get("items", data if isinstance(data, list) else []))}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
async def get_user_permissions(user_id: str) -> dict:
    """Get all permissions for a specific user based on their assigned roles.
    
    Args:
        user_id: The unique identifier of the user (UUID string).
    
    Returns:
        List of permissions the user has.
    """
    try:
        data = await _get_json(f"{ROLE_SERVICE_URL}/api/v1/roles/users/{user_id}/permissions")
        return {"success": True, "user_id": user_id, "permissions": data.get("permissions", data)}
    except Exception as e:
        return {"success": False, "error": str(e), "user_id": user_id}


# ─────────────────────────────────────────────────────────
# AUDIT SERVICE TOOLS
# ─────────────────────────────────────────────────────────

@tool
async def get_audit_logs(
    event_type: Optional[str] = None,
    user_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Retrieve audit log entries with optional filters.
    
    Args:
        event_type: Filter by event type (e.g., 'login', 'signup', 'role_assigned').
        user_id: Filter by user ID.
        source: Filter by source service (e.g., 'auth-service', 'user-service').
        limit: Maximum number of logs to return (max 100).
    
    Returns:
        Audit log entries matching the filters.
    """
    try:
        params = {"limit": min(limit, 100)}
        if event_type: params["event_type"] = event_type
        if user_id: params["user_id"] = user_id
        if source: params["source"] = source
        data = await _get_json(f"{AUDIT_SERVICE_URL}/api/v1/audit/logs", params=params)
        return {"success": True, "logs": data.get("items", []), "total": data.get("total", 0)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
async def get_audit_stats() -> dict:
    """Get aggregated statistics of audit events grouped by event type.
    
    Returns:
        Statistics showing count per event type.
    """
    try:
        data = await _get_json(f"{AUDIT_SERVICE_URL}/api/v1/audit/stats")
        return {"success": True, "stats": data.get("stats", [])}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────
# AI / RAG TOOLS
# ─────────────────────────────────────────────────────────

@tool
async def query_rag(question: str) -> dict:
    """Query the RAG (Retrieval Augmented Generation) system with a question.
    This searches the vector database for relevant context and generates an AI response.
    
    Args:
        question: The question to ask the RAG system.
    
    Returns:
        AI-generated answer with sources and metadata.
    """
    try:
        data = await _post_json(f"{AI_SERVICE_URL}/api/v1/ai/query", {"question": question})
        return {
            "success": True,
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "metadata": data.get("metadata", {}),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
async def ingest_document(title: str, content: str, doc_id: Optional[str] = None) -> dict:
    """Ingest a document into the vector database for RAG queries.
    
    Args:
        title: Title of the document.
        content: The document content text.
        doc_id: Optional unique identifier for the document.
    
    Returns:
        Ingestion result.
    """
    try:
        payload = {
            "documents": [{
                "id": doc_id or title.lower().replace(" ", "_"),
                "title": title,
                "content": content,
                "metadata": {"source": "ai_agent", "ingested_at": datetime.utcnow().isoformat()},
            }]
        }
        data = await _post_json(f"{AI_SERVICE_URL}/api/v1/ai/ingest", payload)
        return {"success": True, "result": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────────────────────

# All available tools for the agent
SYSTEM_TOOLS = [
    get_user_profile,
    list_users,
    search_users,
    list_roles,
    get_user_permissions,
    get_audit_logs,
    get_audit_stats,
    query_rag,
    ingest_document,
]

# Tool descriptions for MCP registration
TOOL_DEFINITIONS = {
    "get_user_profile": {
        "name": "get_user_profile",
        "description": "Get a user's profile by their user ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The unique identifier of the user (UUID string)",
                }
            },
            "required": ["user_id"],
        },
    },
    "list_users": {
        "name": "list_users",
        "description": "List all user profiles in the system",
        "input_schema": {
            "type": "object",
            "properties": {
                "skip": {"type": "integer", "description": "Number of records to skip"},
                "limit": {"type": "integer", "description": "Maximum number of records to return"},
            },
        },
    },
    "search_users": {
        "name": "search_users",
        "description": "Search for users by name or department",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term to match against user names or departments"},
            },
            "required": ["query"],
        },
    },
    "list_roles": {
        "name": "list_roles",
        "description": "List all roles and their associated permissions in the system",
        "input_schema": {"type": "object", "properties": {}},
    },
    "get_user_permissions": {
        "name": "get_user_permissions",
        "description": "Get all permissions for a specific user based on their assigned roles",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "The unique identifier of the user (UUID string)"},
            },
            "required": ["user_id"],
        },
    },
    "get_audit_logs": {
        "name": "get_audit_logs",
        "description": "Retrieve audit log entries with optional filters",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "description": "Filter by event type (e.g., 'login', 'signup')"},
                "user_id": {"type": "string", "description": "Filter by user ID"},
                "source": {"type": "string", "description": "Filter by source service"},
                "limit": {"type": "integer", "description": "Maximum number of logs to return"},
            },
        },
    },
    "get_audit_stats": {
        "name": "get_audit_stats",
        "description": "Get aggregated statistics of audit events grouped by event type",
        "input_schema": {"type": "object", "properties": {}},
    },
    "query_rag": {
        "name": "query_rag",
        "description": "Query the RAG system with a question to get AI-generated answers from documents",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask the RAG system"},
            },
            "required": ["question"],
        },
    },
    "ingest_document": {
        "name": "ingest_document",
        "description": "Ingest a document into the vector database for RAG queries",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the document"},
                "content": {"type": "string", "description": "The document content text"},
                "doc_id": {"type": "string", "description": "Optional unique identifier for the document"},
            },
            "required": ["title", "content"],
        },
    },
}