# ── FastAPI backend ────────────────────────────────────────────────────────────
# Lightweight image (~200 MB) — sentence-transformers/PyTorch are NOT included.
# Reranking is handled by the Cohere API (set COHERE_API_KEY at runtime).
#
# Build:
#   docker build -t rag-api .
#
# Run (with Qdrant Cloud):
#   docker run -p 8000:8000 \
#     -e OPENAI_API_KEY=sk-... \
#     -e QDRANT_URL=https://... \
#     -e QDRANT_API_KEY=... \
#     -e COHERE_API_KEY=... \
#     -v /path/to/chunks.json:/data/chunks.json \
#     -e CHUNKS_DATA_PATH=/data/chunks.json \
#     rag-api
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.10-slim

WORKDIR /app

# Install dependencies (cached layer — only re-runs when requirements change)
COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

# Copy source code
COPY src/ ./src/
COPY scripts/serve.py ./scripts/serve.py

# PYTHONPATH so Python finds the rag_system package under src/
ENV PYTHONPATH=src

# Default port — override with PORT env var (Render sets this automatically)
EXPOSE 8000

CMD ["python", "scripts/serve.py"]
