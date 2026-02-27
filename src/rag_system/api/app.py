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
from ..monitoring.database import init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & config (from environment or defaults)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # rag-system/
_default_chunks = PROJECT_ROOT / "data" / "chunks" / "chunks.json"
_secret_chunks  = Path("/etc/secrets/chunks.json")
# Priority: env var → Render secret file → local default
_chunks_env = os.environ.get("CHUNKS_DATA_PATH")
if _chunks_env:
    CHUNKS_FILE = Path(_chunks_env)
elif _secret_chunks.exists():
    CHUNKS_FILE = _secret_chunks
else:
    CHUNKS_FILE = _default_chunks

API_KEY        = os.environ.get("OPENAI_API_KEY", "")
QDRANT_HOST    = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT    = int(os.environ.get("QDRANT_PORT", "6333"))
# Qdrant Cloud — when QDRANT_URL is set, QDRANT_HOST / QDRANT_PORT are ignored
QDRANT_URL     = os.environ.get("QDRANT_URL") or None
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or None


# ---------------------------------------------------------------------------
# Lifespan — initialise RAG pipeline once at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the RAG pipeline on startup, clean up on shutdown."""
    logger.info("Initialising RAG pipeline...")
    init_db()
    logger.info("Monitoring database ready")
    app.state.generator = ResponseGenerator.from_config(
        api_key=API_KEY,
        chunks_path=CHUNKS_FILE,
        qdrant_host=QDRANT_HOST,
        qdrant_port=QDRANT_PORT,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
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