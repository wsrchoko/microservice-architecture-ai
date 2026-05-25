"""RAG Pipeline Module - Embeddings, Vector Store, and Prompt Engineering.

Extracted from main.py to follow Single Responsibility Principle.
"""
import json
import logging
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

import httpx


logger = logging.getLogger("ai-service.rag")


# ─────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────

MODEL_COST_PER_1K = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "text-embedding-ada-002": {"input": 0.0001, "output": 0.0001},
}

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


# ─────────────────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────────────────

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost for a model call based on token usage."""
    costs = MODEL_COST_PER_1K.get(model, MODEL_COST_PER_1K["gpt-4o-mini"])
    return round(
        (input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs["output"],
        6,
    )


def build_rag_prompt(question: str, context_chunks: List[str]) -> List[dict]:
    """Build a chat prompt with system instructions, few-shot examples, and RAG context."""
    context = "\n\n".join(
        [f"Context {i+1}: {chunk}" for i, chunk in enumerate(context_chunks)]
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": FEW_SHOT_EXAMPLES},
        {
            "role": "user",
            "content": f"Context information:\n{context}\n\nQuestion: {question}\n\nAnswer based on the context provided.",
        },
    ]


# ─────────────────────────────────────────────────────────
# Vector Store Manager (Qdrant)
# ─────────────────────────────────────────────────────────

class VectorStoreManager:
    """Manages interactions with Qdrant vector database for document storage and retrieval."""

    def __init__(self, qdrant_url: str):
        self.qdrant_url = qdrant_url.rstrip("/")

    async def ensure_collection(self, collection_name: str, vector_size: int = 1536) -> bool:
        """Create a collection if it doesn't exist."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.qdrant_url}/collections/{collection_name}")
            if resp.status_code == 200:
                return True

            create_data = {
                "name": collection_name,
                "vectors": {"size": vector_size, "distance": "Cosine"},
            }
            resp = await client.put(
                f"{self.qdrant_url}/collections/{collection_name}", json=create_data
            )
            if resp.status_code == 200:
                logger.info(f"Created Qdrant collection: {collection_name}")
                return True
            logger.error(
                f"Failed to create collection: {resp.status_code} - {resp.text}"
            )
            return False

    async def upsert_points(self, collection_name: str, points: List[dict]) -> bool:
        """Insert or update points in a collection."""
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.qdrant_url}/collections/{collection_name}/points",
                json={"points": points},
            )
            return resp.status_code == 200

    async def search(
        self, collection_name: str, query_vector: List[float], limit: int = 5
    ) -> List[dict]:
        """Search for similar vectors in a collection."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.qdrant_url}/collections/{collection_name}/points/search",
                json={
                    "vector": query_vector,
                    "limit": limit,
                    "with_payload": True,
                },
            )
            if resp.status_code != 200:
                logger.warning(f"Qdrant search failed: {resp.status_code}")
                return []
            data = resp.json()
            return [
                {
                    "id": r["id"],
                    "score": r["score"],
                    "payload": r.get("payload", {}),
                }
                for r in data.get("result", [])
            ]


# ─────────────────────────────────────────────────────────
# OpenAI Helper
# ─────────────────────────────────────────────────────────

class OpenAIHelper:
    """Helper for OpenAI API calls: embeddings and chat completions."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self._embedding_model = "text-embedding-ada-002"

    async def create_embeddings(
        self, texts: List[str]
    ) -> Optional[List[List[float]]]:
        """Create embeddings for a list of texts.

        Falls back to mock embeddings if no API key is configured.
        """
        if not self.api_key:
            logger.warning("OpenAI API key not set - returning mock embeddings")
            return [[0.0] * 1536 for _ in texts]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers,
                json={
                    "model": self._embedding_model,
                    "input": texts,
                },
            )
            if resp.status_code != 200:
                logger.error(f"OpenAI embeddings error: {resp.status_code} - {resp.text}")
                return None

            data = resp.json()
            return [item["embedding"] for item in data["data"]]

    async def chat_completion(
        self,
        messages: List[dict],
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> Optional[dict]:
        """Get a chat completion from OpenAI.

        Falls back to mock response if no API key is configured.
        Returns dict with keys: content, total_tokens, prompt_tokens, completion_tokens
        """
        if not self.api_key:
            return {
                "content": "OpenAI API key not configured. This is a mock response.",
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if resp.status_code != 200:
                logger.error(f"OpenAI chat error: {resp.status_code} - {resp.text}")
                return None

            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})

            return {
                "content": choice["message"]["content"],
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }


# ─────────────────────────────────────────────────────────
# RAG Pipeline
# ─────────────────────────────────────────────────────────

class RAGPipeline:
    """Orchestrates the full RAG flow: embed query → search vectors → build prompt → generate answer."""

    def __init__(
        self,
        vector_store: VectorStoreManager,
        openai_helper: OpenAIHelper,
        model: str,
        default_collection: str = "nexus_documents",
    ):
        self.vector_store = vector_store
        self.openai_helper = openai_helper
        self.model = model
        self.default_collection = default_collection

    async def query(
        self,
        question: str,
        collection: Optional[str] = None,
    ) -> dict:
        """Execute a RAG query end-to-end.

        Returns:
            dict with keys: answer, sources, metadata (latency_ms, total_tokens, cost_usd, model)
        """
        start_time = time.time()
        collection = collection or self.default_collection

        # 1. Create embedding for the question
        question_embedding = await self.openai_helper.create_embeddings([question])
        if not question_embedding:
            raise RuntimeError("Failed to create embedding for question")

        # 2. Search for similar documents in vector store
        search_results = await self.vector_store.search(
            collection, question_embedding[0], limit=5
        )

        context_chunks = [
            r["payload"].get("content", "")
            for r in search_results
            if r.get("payload", {}).get("content")
        ]

        # 3. Build prompt with RAG context
        messages = build_rag_prompt(question, context_chunks)

        # 4. Get completion from OpenAI
        completion = await self.openai_helper.chat_completion(
            messages,
            max_tokens=1000,
            temperature=0.3,
        )
        if not completion:
            raise RuntimeError("Failed to get AI completion")

        elapsed_ms = (time.time() - start_time) * 1000
        cost = calculate_cost(
            self.model,
            completion.get("prompt_tokens", 0),
            completion.get("completion_tokens", 0),
        )

        logger.info(
            f"RAG query completed",
            extra={
                "latency_ms": round(elapsed_ms, 2),
                "tokens": completion.get("total_tokens", 0),
                "cost": cost,
            },
        )

        sources = [
            {
                "id": r["id"],
                "score": r["score"],
                "title": r["payload"].get("title", ""),
            }
            for r in search_results[:3]
        ]

        return {
            "answer": completion["content"],
            "sources": sources,
            "metadata": {
                "model": self.model,
                "latency_ms": round(elapsed_ms, 2),
                "total_tokens": completion.get("total_tokens", 0),
                "cost_usd": cost,
            },
        }

    async def ingest(self, documents: List[dict], collection: Optional[str] = None) -> dict:
        """Ingest documents into the vector store.

        Args:
            documents: List of dicts with keys: id, title, content, metadata (optional)
            collection: Target collection name

        Returns:
            dict with ingestion result
        """
        collection = collection or self.default_collection

        # Ensure collection exists
        await self.vector_store.ensure_collection(collection)

        # Extract texts for embedding
        texts = [doc.get("content", "") for doc in documents]

        # Create embeddings
        embeddings = await self.openai_helper.create_embeddings(texts)
        if not embeddings:
            raise RuntimeError("Failed to create embeddings")

        # Build points for Qdrant
        points = [
            {
                "id": doc.get("id", i),
                "vector": embedding,
                "payload": {
                    "title": doc.get("title", ""),
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }
            for i, (doc, embedding) in enumerate(zip(documents, embeddings))
        ]

        # Upsert to Qdrant
        success = await self.vector_store.upsert_points(collection, points)
        if not success:
            raise RuntimeError("Failed to store documents in vector database")

        return {
            "message": f"Successfully ingested {len(points)} documents",
            "collection": collection,
        }

    async def evaluate(self, question: str, collection: Optional[str] = None) -> dict:
        """Evaluate a query with detailed metrics.

        Returns:
            dict with metrics: latency_ms, total_tokens, input_tokens, output_tokens, cost_usd, source_count
        """
        start_time = time.time()
        collection = collection or self.default_collection

        emb = await self.openai_helper.create_embeddings([question])
        embedding = emb[0] if emb else [0.0] * 1536

        results = await self.vector_store.search(collection, embedding, limit=3)
        contexts = [
            r["payload"].get("content", "")
            for r in results
            if r.get("payload")
        ]

        messages = build_rag_prompt(question, contexts)
        completion = await self.openai_helper.chat_completion(
            messages, max_tokens=1000, temperature=0.3
        )

        elapsed_ms = (time.time() - start_time) * 1000

        if not completion:
            raise RuntimeError("Failed to get completion")

        cost = calculate_cost(
            self.model,
            completion.get("prompt_tokens", 0),
            completion.get("completion_tokens", 0),
        )

        return {
            "response": completion["content"],
            "latency_ms": round(elapsed_ms, 2),
            "total_tokens": completion.get("total_tokens", 0),
            "input_tokens": completion.get("prompt_tokens", 0),
            "output_tokens": completion.get("completion_tokens", 0),
            "cost_usd": cost,
            "source_count": len(results),
        }