# RAG System with Docling

A Retrieval-Augmented Generation system for company documents using Docling for document parsing.

## Features

- PDF document ingestion with Docling
- Structured content extraction (markdown, tables, sections)
- Docker support for reproducible environments

## Setup
```bash
# Install dependencies
uv sync

# Run document ingestion
make ingest
```

## Docker Usage
```bash
# Build Docker image
make docker-build

# Run container
make docker-run

# Run ingestion in Docker
make docker-ingest
```

## Project Structure

- `data/raw/` - Place your PDF files here
- `data/processed/` - Processed documents output
- `src/rag_system/` - Core application code
- `scripts/` - Utility scripts