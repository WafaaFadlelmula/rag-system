"""
Script: serve.py
=================
Starts the FastAPI server.

Run from project root:
    python scripts/serve.py
    
Or via Makefile:
    make serve
"""

import os
import sys
from pathlib import Path

# Load .env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import uvicorn

if __name__ == "__main__":
    # Render (and most PaaS) injects the port via $PORT; default to 8000 locally.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "rag_system.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )