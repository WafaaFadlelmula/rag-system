"""
FastAPI Routes
===============
Endpoints:
  GET  /health           — system health check
  POST /query            — ask a question (blocking)
  POST /query/stream     — ask a question (streaming, SSE)
  GET  /monitor/queries  — fetch all logged queries
  POST /monitor/flag/{id} — toggle the review flag on a query
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .models import QueryRequest, QueryResponse, SourceChunk, HealthResponse, ErrorResponse
from ..monitoring.database import log_query, get_all_queries, flag_query

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Bearer-token auth dependency
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)


def _require_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> None:
    """Check Authorization: Bearer <token>.

    If API_BEARER_TOKEN is not set on the server (local dev), auth is skipped.
    Otherwise any request without a matching token receives 401.
    """
    token: str | None = getattr(request.app.state, "api_bearer_token", None)
    if token is None:
        return  # auth disabled — local dev mode
    if credentials is None or credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _top_reranker_score(sources: list) -> float | None:
    """Return the rerank_score of the highest-ranked source, or None."""
    if not sources:
        return None
    first = sources[0]
    # works for both dict (raw) and SourceChunk (pydantic)
    score = first.get("rerank_score") if isinstance(first, dict) else first.rerank_score
    return score


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health(request: Request):
    """Check if the RAG system and Qdrant are running correctly."""
    gen = request.app.state.generator

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


# ---------------------------------------------------------------------------
# Query (blocking)
# ---------------------------------------------------------------------------

@router.post("/query", response_model=QueryResponse, tags=["RAG"],
             dependencies=[Depends(_require_token)])
async def query(request: Request, body: QueryRequest):
    """
    Ask a question and get a full answer with sources.
    Runs the complete pipeline: vector search → BM25 → rerank → LLM.
    Every call is automatically logged to the monitoring database.
    """
    gen = request.app.state.generator

    try:
        logger.info(f"Query: {body.question[:80]}")
        t0 = time.perf_counter()
        response = gen.answer(body.question, top_k=body.top_k)
        latency_ms = (time.perf_counter() - t0) * 1000

        sources_raw = response.sources  # list[dict] from the generator
        top_score = _top_reranker_score(sources_raw)

        # Persist to monitoring DB (fire-and-forget; errors are non-fatal)
        try:
            log_query(
                question=response.question,
                answer=response.answer,
                sources=sources_raw,
                cost_usd=response.cost_usd,
                latency_ms=latency_ms,
                top_reranker_score=top_score,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )
        except Exception as db_err:
            logger.warning(f"Monitoring DB write failed: {db_err}")

        return QueryResponse(
            question=response.question,
            answer=response.answer,
            sources=_format_sources(sources_raw),
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_usd=response.cost_usd,
        )
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Query (streaming SSE)
# ---------------------------------------------------------------------------

@router.post("/query/stream", tags=["RAG"],
             dependencies=[Depends(_require_token)])
async def query_stream(request: Request, body: QueryRequest):
    """
    Ask a question and stream the answer token by token (Server-Sent Events).
    Sources are sent as a final SSE event after the answer completes.
    The complete query is logged to the monitoring database after streaming ends.
    """
    gen = request.app.state.generator

    def event_stream():
        t0 = time.perf_counter()
        collected: list[str] = []

        try:
            token_iter, sources = gen.stream_answer(body.question)

            for token in token_iter:
                collected.append(token)
                yield f"data: {token}\n\n"

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

            # Log after stream completes; cost/tokens unavailable from stream
            latency_ms = (time.perf_counter() - t0) * 1000
            try:
                log_query(
                    question=body.question,
                    answer="".join(collected),
                    sources=sources,
                    cost_usd=None,
                    latency_ms=latency_ms,
                    top_reranker_score=_top_reranker_score(sources),
                    prompt_tokens=None,
                    completion_tokens=None,
                )
            except Exception as db_err:
                logger.warning(f"Monitoring DB write failed (stream): {db_err}")

        except Exception as e:
            logger.error(f"Stream failed: {e}", exc_info=True)
            yield f"event: error\ndata: {str(e)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Monitoring endpoints
# ---------------------------------------------------------------------------

class FlagRequest(BaseModel):
    flagged: bool


@router.get("/monitor/queries", tags=["Monitoring"],
            dependencies=[Depends(_require_token)])
async def monitor_queries(request: Request):
    """Return all logged queries from the monitoring database."""
    try:
        return get_all_queries()
    except Exception as e:
        logger.error(f"Failed to fetch query logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor/flag/{query_id}", tags=["Monitoring"],
             dependencies=[Depends(_require_token)])
async def monitor_flag(request: Request, query_id: int, body: FlagRequest):
    """Set or clear the review flag on a logged query."""
    try:
        flag_query(query_id, body.flagged)
        return {"ok": True, "id": query_id, "flagged": body.flagged}
    except Exception as e:
        logger.error(f"Failed to update flag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
