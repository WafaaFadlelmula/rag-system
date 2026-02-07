FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Docling
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project configuration files
COPY pyproject.toml ./
COPY README.md ./

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Copy .env if exists
COPY .env ./


# Install dependencies
RUN uv sync

# Create data directories
RUN mkdir -p data/raw data/processed data/chunks

CMD ["bash"]