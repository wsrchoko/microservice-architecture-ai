"""AI Service - RAG + LangGraph Agent + MCP Server.

Architecture:
- app/rag.py: RAG pipeline (embeddings, vector store, prompt engineering)
- app/tools.py: Function calling tools for agent (9 tools across 4 microservices)
- app/agent.py: LangGraph multi-step agent with state graph
- app/mcp_server.py: Model Context Protocol server for external AI agents
- app/main.py: FastAPI application, DI, routing, and configuration
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from app.rag import VectorStoreManager, OpenAIHelper, RAGPipeline
from app.mcp_server import handle_mcp_request


# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────

class Settings(BaseSettings):
    """AI Service configuration, loaded from environment variables."""
    service_name: str = "ai-service"
    service_version: str = "2.0.0"
    log_level: str = "INFO"
    qdrant_url: str = "http://localhost:6333"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    auth_service_url: str = "http://localhost:8001"
    user_service_url: str = "http://localhost:8002"
    role_service_url: str = "http://localhost:8003"
    audit_service_url: str = "http://localhost:8004"
    max_tokens: int = 1000
    temperature: float = 0.3
    max_agent_tool_calls: int = 10

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

# Setup structured logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(settings.service_name)


# ─────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    collection: str = "nexus_documents"

class DocumentIngestRequest(BaseModel):
    documents: List[dict] = Field(..., description="List of documents with id, content, metadata")
    collection: str = "nexus_documents"

class AIResponse(BaseModel):
    answer: str
    sources: List[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

class QueryEvaluation(BaseModel):
    response: str
    latency_ms: float
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    source_count: int

class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None,
        description='Previous messages: [{"role": "user"|"assistant", "content": "..."}]',
    )

class AgentResponse(BaseModel):
    answer: str
    tool_calls: int = 0
    trace: List[dict] = Field(default_factory=list)
    latency_ms: float = 0.0
    metadata: dict = Field(default_factory=dict)

class MCPRequest(BaseModel):
    type: str = Field(..., description="list_tools | call_tool | list_resources | read_resource")
    params: dict = Field(default_factory=dict)

class MCPResponse(BaseModel):
    type: str
    tools: Optional[List[dict]] = None
    resources: Optional[List[dict]] = None
    content: Optional[List[dict]] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────
# Dependency Injection Container
# ─────────────────────────────────────────────────────────

class Container:
    """Holds service instances initialized at startup."""
    rag_pipeline: Optional[RAGPipeline] = None
    agent: Optional[Any] = None
    settings: Settings = settings

_container = Container()


def _init_agent():
    """Lazy initialization of the LangGraph agent."""
    if _container.agent is None and settings.openai_api_key:
        from app.agent import NexusAgent
        _container.agent = NexusAgent(
            openai_api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tool_calls=settings.max_agent_tool_calls,
        )
        logger.info("LangGraph NexusAgent initialized")
    return _container.agent


# ─────────────────────────────────────────────────────────
# Application Lifespan
# ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize services. Shutdown: clean up resources."""
    logger.info(f"Starting {settings.service_name} v{settings.service_version}")

    # Initialize RAG pipeline
    try:
        vector_store = VectorStoreManager(settings.qdrant_url)
        openai_helper = OpenAIHelper(settings.openai_api_key, settings.openai_model)
        await vector_store.ensure_collection("nexus_documents")
        _container.rag_pipeline = RAGPipeline(
            vector_store=vector_store,
            openai_helper=openai_helper,
            model=settings.openai_model,
        )
        logger.info("RAG pipeline initialized")
    except Exception as e:
        logger.warning(f"RAG initialization incomplete: {e}")

    # Pre-initialize agent if API key available
    if settings.openai_api_key:
        _init_agent()

    logger.info(f"{settings.service_name} started (model: {settings.openai_model})")
    yield
    logger.info(f"{settings.service_name} stopped")


app = FastAPI(
    title="Nexus AI Service",
    description="AI Agent with RAG + LangGraph Agent + MCP Server",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────
# Exception Handlers
# ─────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        extra={"path": str(request.url), "method": request.method, "error": str(exc)},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred", "error_code": "INTERNAL_ERROR"},
    )


# ─────────────────────────────────────────────────────────
# RAG Endpoints
# ─────────────────────────────────────────────────────────

@app.post("/api/v1/ai/query", response_model=AIResponse)
async def query_rag(request: QueryRequest):
    """RAG query: search vector DB for context and generate AI response."""
    pipeline = _container.rag_pipeline
    if not pipeline:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        result = await pipeline.query(
            question=request.question,
            collection=request.collection,
        )
        return AIResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        raise HTTPException(status_code=500, detail="RAG query failed")


@app.post("/api/v1/ai/ingest")
async def ingest_documents(request: DocumentIngestRequest):
    """Ingest documents into Qdrant vector database."""
    pipeline = _container.rag_pipeline
    if not pipeline:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        result = await pipeline.ingest(
            documents=request.documents,
            collection=request.collection,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail="Document ingestion failed")


@app.post("/api/v1/ai/evaluate", response_model=QueryEvaluation)
async def evaluate_rag_query(request: QueryRequest):
    """Evaluate a RAG query with detailed metrics (latency, tokens, cost)."""
    pipeline = _container.rag_pipeline
    if not pipeline:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    try:
        result = await pipeline.evaluate(
            question=request.question,
            collection=request.collection,
        )
        return QueryEvaluation(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Evaluate error: {e}")
        raise HTTPException(status_code=500, detail="Evaluation failed")


# ─────────────────────────────────────────────────────────
# LangGraph Agent Endpoint
# ─────────────────────────────────────────────────────────

@app.post("/api/v1/ai/agent", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    """Run the LangGraph multi-step agent that orchestrates calls across all microservices.

    The agent uses function calling to decide which tools to call based on the query:
    - User profiles, search, listing
    - Roles and permissions
    - Audit logs and statistics
    - RAG knowledge base queries

    Example queries:
    - "Show me all users and their roles"
    - "What permissions does user X have?"
    - "Show me recent audit logs for login events"
    - "How many users are registered and what roles exist?"
    """
    agent = _init_agent()
    if not agent:
        raise HTTPException(
            status_code=503,
            detail=(
                "Agent not available. "
                "Set the OPENAI_API_KEY environment variable and restart the service."
            ),
        )

    try:
        start_time = time.time()
        result = await agent.run(
            query=request.query,
            conversation_history=request.conversation_history,
        )
        return AgentResponse(
            answer=result["answer"],
            tool_calls=result["tool_calls"],
            trace=result["trace"],
            latency_ms=result["latency_ms"],
            metadata=result["metadata"],
        )
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


# ─────────────────────────────────────────────────────────
# MCP Protocol Endpoints
# ─────────────────────────────────────────────────────────

@app.post("/api/v1/ai/mcp", response_model=MCPResponse)
async def mcp_handler(request: MCPRequest):
    """Model Context Protocol (MCP) endpoint for external AI agents.

    Allows tools like Claude Code, Cursor, etc. to discover and call Nexus system tools.

    Request types:
    - list_tools: List all tools with JSON schemas
    - call_tool: Execute a tool by name with arguments
    - list_resources: List available system resources
    - read_resource: Read a resource by URI (e.g., nexus://system/status)

    Examples:
    ```json
    {"type": "list_tools", "params": {}}
    {"type": "call_tool", "params": {"name": "list_users", "arguments": {}}}
    {"type": "read_resource", "params": {"uri": "nexus://system/status"}}
    ```
    """
    try:
        result = await handle_mcp_request({
            "type": request.type,
            "params": request.params,
        })
        return MCPResponse(**result)
    except Exception as e:
        logger.error(f"MCP error: {e}")
        return MCPResponse(type="error", error=str(e))


@app.get("/api/v1/ai/mcp/config")
async def mcp_config():
    """Get MCP server configuration for external agent registration."""
    tools = [
        {"name": "get_user_profile", "description": "Get a user's profile by their user ID"},
        {"name": "list_users", "description": "List all user profiles in the system"},
        {"name": "search_users", "description": "Search for users by name or department"},
        {"name": "list_roles", "description": "List all roles and their permissions"},
        {"name": "get_user_permissions", "description": "Get permissions for a specific user"},
        {"name": "get_audit_logs", "description": "Retrieve audit log entries with filters"},
        {"name": "get_audit_stats", "description": "Get aggregated audit event statistics"},
        {"name": "query_rag", "description": "Query the RAG system with a question"},
        {"name": "ingest_document", "description": "Ingest a document into the vector database"},
    ]
    return {
        "name": "nexus-ai-service",
        "version": settings.service_version,
        "description": "Nexus System MCP Server - Access users, roles, audit logs, and RAG knowledge base",
        "endpoint": "/api/v1/ai/mcp",
        "protocol": "mcp",
        "config_url": "/api/v1/ai/mcp",
        "tools": tools,
    }


# ─────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────

@app.get("/api/v1/ai/health")
async def health():
    """Health check endpoint returning service status and available capabilities."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "model": settings.openai_model,
        "qdrant": settings.qdrant_url,
        "agent_available": _init_agent() is not None,
        "rag_available": _container.rag_pipeline is not None,
        "capabilities": {
            "rag": True,
            "agent": _init_agent() is not None,
            "mcp": True,
        },
        "endpoints": {
            "rag_query": "POST /api/v1/ai/query",
            "rag_ingest": "POST /api/v1/ai/ingest",
            "rag_evaluate": "POST /api/v1/ai/evaluate",
            "agent": "POST /api/v1/ai/agent",
            "mcp": "POST /api/v1/ai/mcp",
            "mcp_config": "GET /api/v1/ai/mcp/config",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level="info",
    )