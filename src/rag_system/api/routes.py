"""
FastAPI Routes
===============
Endpoints:
  GET  /health      — system health check
  POST /query       — ask a question (blocking)
  POST /query/stream — ask a question (streaming)
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .models import QueryRequest, QueryResponse, SourceChunk, HealthResponse, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_sources(chunks: list[dict]) -> list[SourceChunk]:
    return [
        SourceChunk(
            source_file=c.get("source_file", ""),
            headers=c.get("headers", []),
            text=c.get("text", ""),
            rerank_score=c.get("rerank_score"),
            hybrid_score=c.get("hybrid_score"),
            chunk_type=c.get("chunk_type", ""),
        )
        for c in chunks
    ]


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health(request: Request):
    """Check if the RAG system and Qdrant are running correctly."""
    gen = request.app.state.generator

    # Ping Qdrant
    try:
        info = gen.retriever.store.collection_info()
        qdrant_status = f"ok ({info['points_count']} points)"
    except Exception as e:
        qdrant_status = f"error: {e}"

    return HealthResponse(
        status="ok",
        qdrant=qdrant_status,
        chunks_loaded=len(gen.hybrid.chunks),
        model=gen.llm.cfg.model,
    )


@router.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query(request: Request, body: QueryRequest):
    """
    Ask a question and get a full answer with sources.
    Runs the complete pipeline: vector search → BM25 → rerank → LLM.
    """
    gen = request.app.state.generator

    try:
        logger.info(f"Query: {body.question[:80]}")
        response = gen.answer(body.question)

        return QueryResponse(
            question=response.question,
            answer=response.answer,
            sources=_format_sources(response.sources),
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_usd=response.cost_usd,
        )
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream", tags=["RAG"])
async def query_stream(request: Request, body: QueryRequest):
    """
    Ask a question and stream the answer token by token (Server-Sent Events).
    Sources are sent as a final SSE event after the answer completes.
    """
    gen = request.app.state.generator

    def event_stream():
        try:
            token_iter, sources = gen.stream_answer(body.question)

            # Stream answer tokens
            for token in token_iter:
                yield f"data: {token}\n\n"

            # Send sources as final event
            import json
            sources_data = [
                {
                    "source_file": s.get("source_file", ""),
                    "headers": s.get("headers", []),
                    "rerank_score": s.get("rerank_score"),
                }
                for s in sources
            ]
            yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"
            yield "event: done\ndata: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )