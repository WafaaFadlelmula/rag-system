.PHONY: install test format ingest chunk pipeline docker-build docker-run

install:
	uv sync

test:
	uv run pytest tests/ -v

format:
	uv run black src/ scripts/
	uv run ruff check --fix src/

ingest:
	uv run python scripts/ingest_documents.py

chunk:
	uv run python scripts/create_chunks.py

embed:
	uv run python scripts/create_embeddings.py


vectordb-up:
	docker compose -f docker/docker-compose.yml up -d

vectordb-down:
	docker compose -f docker/docker-compose.yml down

populate:
	uv run python scripts/populate_vectordb.py

test-retrieval:
	uv run python scripts/test_retrieval.py

ask:
	uv run python scripts/ask.py

ask-stream:
	uv run python scripts/ask.py --stream

serve:
	uv run python scripts/serve.py

pipeline: ingest chunk

docker-build:
	docker build -f docker/Dockerfile -t rag-system-docling .

docker-run:
	docker-compose -f docker/docker-compose.yml up -d

docker-ingest:
	docker-compose -f docker/docker-compose.yml exec rag-system uv run python scripts/ingest_documents.py

docker-stop:
	docker-compose -f docker/docker-compose.yml down

view-markdown:
	ls data/processed/markdown/*.md

view-chunks:
	cat data/chunks/chunking_stats.json