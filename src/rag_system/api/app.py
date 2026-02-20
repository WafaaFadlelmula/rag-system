"""
FastAPI Application
====================
Entry point for the RAG API server.

Run with:
    uvicorn rag_system.api.app:app --host 0.0.0.0 --port 8000 --reload

Or via:
    make serve
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from ..generation.response_generator import ResponseGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & config (from environment or defaults)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # rag-system/
CHUNKS_FILE  = PROJECT_ROOT / "data" / "chunks" / "chunks.json"

API_KEY      = os.environ.get("OPENAI_API_KEY", "")
QDRANT_HOST  = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT  = int(os.environ.get("QDRANT_PORT", "6333"))


# ---------------------------------------------------------------------------
# Lifespan — initialise RAG pipeline once at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the RAG pipeline on startup, clean up on shutdown."""
    logger.info("Initialising RAG pipeline...")
    app.state.generator = ResponseGenerator.from_config(
        api_key=API_KEY,
        chunks_path=CHUNKS_FILE,
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
    )
    logger.info("RAG pipeline ready")
    yield
    logger.info("Shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ECOICE RAG API",
    description="Retrieval-Augmented Generation API for ECOICE project documents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Root redirect to docs
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")