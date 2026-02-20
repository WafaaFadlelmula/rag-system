"""
API Request / Response Models
================================
Pydantic models for FastAPI endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Question to ask the RAG system")
    top_k: Optional[int] = Field(default=5, ge=1, le=20, description="Number of source chunks to retrieve")
    stream: Optional[bool] = Field(default=False, description="Stream the response token by token")


class SourceChunk(BaseModel):
    source_file: str
    headers: list[str]
    text: str
    rerank_score: Optional[float] = None
    hybrid_score: Optional[float] = None
    chunk_type: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceChunk]
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    chunks_loaded: int
    model: str


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None