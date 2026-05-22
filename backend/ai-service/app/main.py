"""AI Service - RAG Agent with OpenAI and Qdrant."""
import os, json, logging, time
from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import httpx


class Settings(BaseSettings):
    service_name: str = "ai-service"
    service_version: str = "1.0.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://nexus_user:nexus_secure_password_2025@localhost:5432/nexusdb"
    rabbitmq_url: str = "amqp://nexus_user:nexus_rabbit_password@localhost:5672/"
    qdrant_url: str = "http://localhost:6333"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    auth_service_url: str = "http://localhost:8001"
    user_service_url: str = "http://localhost:8002"
    max_tokens: int = 1000
    temperature: float = 0.3
    class Config: env_file = ".env"; extra = "ignore"

settings = Settings()

# Setup logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(settings.service_name)

# Global clients
openai_client = None
qdrant_client = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None
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


class VectorStoreManager:
    def __init__(self, qdrant_url: str):
        self.qdrant_url = qdrant_url
        self.collections = {}

    async def ensure_collection(self, collection_name: str, vector_size: int = 1536):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.qdrant_url}/collections/{collection_name}")
            if resp.status_code == 200:
                return
            create_data = {"name": collection_name, "vectors": {"size": vector_size, "distance": "Cosine"}}
            resp = await client.put(f"{self.qdrant_url}/collections/{collection_name}", json=create_data)
            if resp.status_code == 200:
                logger.info(f"Created collection: {collection_name}")

    async def upsert_points(self, collection_name: str, points: List[dict]):
        async with httpx.AsyncClient() as client:
            resp = await client.put(f"{self.qdrant_url}/collections/{collection_name}/points", json={"points": points})
            return resp.status_code == 200

    async def search(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.qdrant_url}/collections/{collection_name}/points/search",
                json={"vector": query_vector, "limit": limit, "with_payload": True},
            )
            if resp.status_code != 200: return []
            data = resp.json()
            return [{"id": r["id"], "score": r["score"], "payload": r.get("payload", {})} for r in data.get("result", [])]


class OpenAIHelper:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def create_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self.api_key:
            logger.warning("OpenAI API key not set - returning mock embeddings")
            return [[0.0] * 1536 for _ in texts]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": "text-embedding-ada-002", "input": texts},
                timeout=30.0,
            )
            if resp.status_code != 200: logger.error(f"OpenAI embeddings error: {resp.text}"); return None
            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    async def chat_completion(self, messages: List[dict], max_tokens: int = 1000, temperature: float = 0.3) -> Optional[dict]:
        if not self.api_key:
            return {"content": "OpenAI API key not configured. This is a mock response.", "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
                timeout=60.0,
            )
            if resp.status_code != 200: logger.error(f"OpenAI chat error: {resp.text}"); return None
            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return {"content": choice["message"]["content"], "total_tokens": usage.get("total_tokens", 0),
                    "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)}


SYSTEM_PROMPT = """You are a helpful AI assistant for the Nexus User Management System. 
You help users understand and interact with the system's data.

Guidelines:
1. Always respond in a clear, professional manner
2. Use the provided context to answer questions accurately
3. If you don't have enough information, say so honestly
4. Do not invent or hallucinate information not present in the context
5. When discussing user data, respect privacy and security
6. Keep responses concise and actionable
"""

FEW_SHOT_EXAMPLES = """
Example 1:
User: How many users are in the system?
Assistant: Based on the system data, the user management system tracks user profiles. 
You can query user statistics through the User Service API.

Example 2:
User: What can you help me with?
Assistant: I can help you with:
- Answering questions about system users and data
- Generating reports from user information
- Explaining system features and capabilities
- Analyzing user patterns and trends
"""


def build_rag_prompt(question: str, context_chunks: List[str]) -> List[dict]:
    context = "\n\n".join([f"Context {i+1}: {chunk}" for i, chunk in enumerate(context_chunks)])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": FEW_SHOT_EXAMPLES},
        {"role": "user", "content": f"Context information:\n{context}\n\nQuestion: {question}\n\nAnswer based on the context provided."}
    ]


MODEL_COST_PER_1K = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0001},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = MODEL_COST_PER_1K.get(model, MODEL_COST_PER_1K["gpt-4o-mini"])
    return round((input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs["output"], 6)


vector_store: Optional[VectorStoreManager] = None
openai_helper: Optional[OpenAIHelper] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vector_store, openai_helper
    logger.info("Starting AI Service")
    vector_store = VectorStoreManager(settings.qdrant_url)
    openai_helper = OpenAIHelper(settings.openai_api_key, settings.openai_model)
    try:
        await vector_store.ensure_collection("nexus_documents")
    except Exception as e:
        logger.warning(f"Could not create Qdrant collection: {e}")
    logger.info(f"AI Service started (model: {settings.openai_model})")
    yield
    logger.info("AI Service stopped")


app = FastAPI(title="Nexus AI Service", description="AI Agent with RAG", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.post("/api/v1/ai/query", response_model=AIResponse)
async def query_ai(request: QueryRequest):
    if not vector_store or not openai_helper:
        raise HTTPException(status_code=503, detail="AI Service not fully initialized")
    start_time = time.time()
    try:
        question_embedding = await openai_helper.create_embeddings([request.question])
        if not question_embedding: raise HTTPException(status_code=500, detail="Failed to create embedding")
        search_results = await vector_store.search(request.collection, question_embedding[0], limit=5)
        context_chunks = [r["payload"].get("content", "") for r in search_results if r.get("payload", {}).get("content")]
        messages = build_rag_prompt(request.question, context_chunks)
        completion = await openai_helper.chat_completion(messages, max_tokens=settings.max_tokens, temperature=settings.temperature)
        if not completion: raise HTTPException(status_code=500, detail="Failed to get AI completion")
        elapsed_ms = (time.time() - start_time) * 1000
        cost = calculate_cost(settings.openai_model, completion.get("prompt_tokens", 0), completion.get("completion_tokens", 0))
        logger.info(f"AI query completed", extra={"latency_ms": round(elapsed_ms, 2), "tokens": completion.get("total_tokens", 0), "cost": cost})
        sources = [{"id": r["id"], "score": r["score"], "title": r["payload"].get("title", "")} for r in search_results[:3]]
        return AIResponse(answer=completion["content"], sources=sources, metadata={
            "model": settings.openai_model, "latency_ms": round(elapsed_ms, 2),
            "total_tokens": completion.get("total_tokens", 0), "cost_usd": cost,
        })
    except HTTPException: raise
    except Exception as e:
        logger.error(f"AI query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ai/ingest")
async def ingest_documents(request: DocumentIngestRequest):
    if not vector_store or not openai_helper:
        raise HTTPException(status_code=503, detail="AI Service not fully initialized")
    try:
        await vector_store.ensure_collection(request.collection)
        texts = [doc.get("content", "") for doc in request.documents]
        embeddings = await openai_helper.create_embeddings(texts)
        if not embeddings: raise HTTPException(status_code=500, detail="Failed to create embeddings")
        points = [{"id": doc.get("id", i), "vector": embedding,
                    "payload": {"title": doc.get("title", ""), "content": doc.get("content", ""),
                               "metadata": doc.get("metadata", {}), "timestamp": datetime.utcnow().isoformat()}}
                  for i, (doc, embedding) in enumerate(zip(request.documents, embeddings))]
        success = await vector_store.upsert_points(request.collection, points)
        if not success: raise HTTPException(status_code=500, detail="Failed to store documents")
        return {"message": f"Successfully ingested {len(points)} documents", "collection": request.collection}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ai/evaluate")
async def evaluate_query(request: QueryRequest):
    start_time = time.time()
    if not vector_store or not openai_helper:
        raise HTTPException(status_code=503, detail="AI Service not initialized")
    emb = await openai_helper.create_embeddings([request.question])
    embedding = emb[0] if emb else [0.0] * 1536
    results = await vector_store.search(request.collection, embedding, limit=3)
    contexts = [r["payload"].get("content", "") for r in results if r.get("payload")]
    messages = build_rag_prompt(request.question, contexts)
    completion = await openai_helper.chat_completion(messages, max_tokens=settings.max_tokens, temperature=settings.temperature)
    elapsed_ms = (time.time() - start_time) * 1000
    if not completion: raise HTTPException(status_code=500, detail="Failed to get completion")
    cost = calculate_cost(settings.openai_model, completion.get("prompt_tokens", 0), completion.get("completion_tokens", 0))
    return QueryEvaluation(response=completion["content"], latency_ms=round(elapsed_ms, 2),
                          total_tokens=completion.get("total_tokens", 0), input_tokens=completion.get("prompt_tokens", 0),
                          output_tokens=completion.get("completion_tokens", 0), cost_usd=cost, source_count=len(results))


@app.get("/api/v1/ai/health")
async def health():
    return {"status": "healthy", "service": "ai-service", "version": "1.0.0", "model": settings.openai_model, "qdrant": settings.qdrant_url}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=True)