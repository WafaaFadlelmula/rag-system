.PHONY: install test format ingest docker-build docker-run

install:
	uv sync

test:
	uv run pytest tests/ -v

format:
	uv run black src/ scripts/
	uv run ruff check --fix src/

ingest:
	uv run python scripts/ingest_documents.py

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