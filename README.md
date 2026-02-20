# RAG System

A production-ready **Retrieval-Augmented Generation (RAG)** system built for the a project deliverables, enabling natural language Q&A over technical milestone reports using hybrid search and cross-encoder reranking.

---

## Architecture

![RAG System Architecture](docs/architecture.svg)

## Tech Stack

| Component | Technology |
|---|---|
| PDF Parsing | [Docling](https://github.com/DS4SD/docling) |
| Chunking | Hybrid (Semantic + Fixed-size with overlap) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Vector Database | [Qdrant](https://qdrant.tech/) (Docker) |
| Keyword Search | BM25 (`rank-bm25`) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM | OpenAI `gpt-4o-mini` |
| API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Package Manager | [uv](https://github.com/astral-sh/uv) |

---

## Project Structure

```
rag-system/
├── data/
│   ├── raw/                  # PDF source documents (not in repo)
│   ├── processed/            # Docling output — markdown + JSON
│   ├── chunks/               # Chunked documents
│   ├── embeddings/           # OpenAI embedding vectors
│   └── qdrant/               # Qdrant persistent storage
├── src/rag_system/
│   ├── ingestion/            # PDF loading and chunking
│   │   ├── chunker.py        # Hybrid chunker
│   │   └── preprocessor.py   # Markdown cleaner
│   ├── embeddings/           # OpenAI embedding wrapper
│   │   ├── embedding_model.py
│   │   └── batch_processor.py
│   ├── vectorstore/          # Qdrant integration
│   │   ├── store.py          # Search and upsert
│   │   └── indexer.py        # Index builder
│   ├── retrieval/            # Retrieval pipeline
│   │   ├── retriever.py      # Vector search
│   │   ├── hybrid_search.py  # BM25 + RRF fusion
│   │   └── reranker.py       # Cross-encoder reranker
│   ├── generation/           # LLM answer generation
│   │   ├── llm_client.py     # OpenAI GPT-4o-mini client
│   │   ├── response_generator.py  # Full RAG pipeline
│   │   └── prompts.py        # Prompt templates
│   └── api/                  # FastAPI layer
│       ├── app.py            # Application entry point
│       ├── routes.py         # API endpoints
│       └── models.py         # Request/response models
├── scripts/
│   ├── ingest_documents.py   # Step 1: Parse PDFs
│   ├── create_chunks.py      # Step 2: Chunk documents
│   ├── create_embeddings.py  # Step 3: Generate embeddings
│   ├── populate_vectordb.py  # Step 4: Load into Qdrant
│   ├── test_retrieval.py     # Step 5: Test retrieval pipeline
│   ├── serve.py              # Start FastAPI server
│   └── ask.py                # CLI chat interface
├── frontend/
│   └── streamlit_app.py      # Streamlit chat UI
├── docker/
│   └── docker-compose.yml    # Qdrant + app services
├── .streamlit/
│   └── config.toml           # Streamlit theme
├── pyproject.toml
├── .env                      # API keys (never commit)
└── Makefile
```

---

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker & Docker Compose
- OpenAI API key

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd rag-system
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

`.env` file:
```env
OPENAI_API_KEY="sk-..."
```

### 4. Start Qdrant

```bash
make vectordb-up
```

---

## Running the Pipeline

Run each step in order the first time. After that, only re-run steps when your documents change.

```bash
# Step 1 — Parse PDFs with Docling (AI-powered, ~500MB models downloaded once)
make ingest

# Step 2 — Chunk documents (hybrid semantic + fixed-size)
make chunk

# Step 3 — Generate OpenAI embeddings (~$0.003 for 428 chunks)
make embed

# Step 4 — Load embeddings into Qdrant
make populate

# Or run all pipeline steps at once
make pipeline
```

---

## Running the App

You need two terminals:

```bash
# Terminal 1 — FastAPI backend (port 8000)
make serve

# Terminal 2 — Streamlit frontend (port 8501)
make streamlit
```

Then open **http://localhost:8501** in your browser.

The interactive API docs are available at **http://localhost:8333/docs**.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | System health check |
| `POST` | `/api/v1/query` | Ask a question (blocking) |
| `POST` | `/api/v1/query/stream` | Ask a question (streaming SSE) |

### Example request

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the power consumption of the C-PON system?", "top_k": 5}'
```

### Example response

```json
{
  "question": "What is the power consumption of the C-PON system?",
  "answer": "The C-PON system power consumption increases with traffic load...",
  "sources": [
    {
      "source_file": "MS7_ECOICE Report Final Draft",
      "headers": ["5.2 Power Consumption Measurement"],
      "rerank_score": 7.71
    }
  ],
  "model": "gpt-4o-mini-2024-07-18",
  "prompt_tokens": 2404,
  "completion_tokens": 147,
  "cost_usd": 0.000449
}
```

---

## Makefile Reference

```bash
make install          # Install dependencies
make ingest           # Parse PDFs with Docling
make chunk            # Chunk processed documents
make embed            # Generate OpenAI embeddings
make populate         # Load embeddings into Qdrant
make pipeline         # Run ingest + chunk in sequence
make serve            # Start FastAPI server
make streamlit        # Start Streamlit frontend
make test-retrieval   # Test the retrieval pipeline
make ask              # Interactive CLI chat
make vectordb-up      # Start Qdrant in Docker
make vectordb-down    # Stop Qdrant
make view-chunks      # Inspect chunking stats
make format           # Format code with black + ruff
make test             # Run tests
```

---

## Retrieval Pipeline

The system uses a 3-stage retrieval approach for maximum accuracy:

1. **Vector Search** — embeds the query with OpenAI and finds the top 20 semantically similar chunks from Qdrant
2. **BM25 + RRF** — performs keyword search in parallel and fuses both result lists using Reciprocal Rank Fusion, reducing to top 10
3. **Cross-encoder Reranking** — a local `ms-marco-MiniLM-L-6-v2` model scores each (query, chunk) pair together for maximum precision, returning the final top-k

This hybrid approach is particularly effective for technical documents where both semantic meaning and exact terminology (e.g. "C-PON", "DT15", "OLM") matter.

---

## Chunking Strategy

Documents are chunked using a hybrid strategy:

- **Semantic** — split on markdown headers (`##`, `###`) to respect document structure
- **Merged** — sections smaller than 100 tokens are merged with neighbours to avoid tiny chunks
- **Fixed-split** — sections larger than 800 tokens are split with 150-token overlap, snapping to sentence boundaries

Default settings (tuned for `text-embedding-3-small`):

| Parameter | Value |
|---|---|
| Max chunk tokens | 800 |
| Overlap tokens | 150 |
| Min chunk tokens | 100 |

---

## Cost Estimates

Based on 8 documents / 428 chunks:

| Operation | Cost |
|---|---|
| Embedding (one-time) | ~$0.003 |
| Per query | ~$0.0003–$0.0005 |
| 1,000 queries | ~$0.40 |

---

## Adding New Documents

1. Drop PDF files into `data/raw/`
2. Re-run the pipeline:

```bash
make ingest && make chunk && make embed && make populate
```

> Note: `make populate` will skip recreating the collection by default. To force a full rebuild, change `recreate=False` to `recreate=True` in `scripts/populate_vectordb.py`.

---

## License

MIT