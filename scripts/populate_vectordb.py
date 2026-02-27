"""
Script: populate_vectordb.py
==============================
Run from project root:

    python scripts/populate_vectordb.py

Reads:   data/embeddings/embeddings.json
Writes:  Qdrant collection

Connection is controlled by environment variables — the same ones used by the
FastAPI server, so you can use a .env file or export them in your shell:

    Local Docker (default):
        No env vars needed — connects to localhost:6333

    Qdrant Cloud:
        QDRANT_URL=https://<cluster-id>.cloud.qdrant.io:6333
        QDRANT_API_KEY=<your-api-key>
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")   # load .env before reading os.environ

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient
from rag_system.vectorstore.store import QdrantConfig
from rag_system.vectorstore.indexer import VectorIndexer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT    = Path(__file__).parent.parent
EMBEDDINGS_FILE = PROJECT_ROOT / "data" / "embeddings" / "embeddings.json"
STATS_FILE      = PROJECT_ROOT / "data" / "embeddings" / "vectordb_stats.json"

# ---------------------------------------------------------------------------
# Connection config from environment
# ---------------------------------------------------------------------------
QDRANT_URL     = os.environ.get("QDRANT_URL") or None
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY") or None
QDRANT_HOST    = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT    = int(os.environ.get("QDRANT_PORT", "6333"))

config = QdrantConfig(
    host=QDRANT_HOST,
    port=QDRANT_PORT,
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    collection_name="rag_chunks",
    vector_size=1536,
    default_top_k=5,
)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not EMBEDDINGS_FILE.exists():
        print(f"❌ Embeddings file not found: {EMBEDDINGS_FILE}")
        print("   Run `make embed` first.")
        sys.exit(1)

    print(f"📦 Loading embeddings from {EMBEDDINGS_FILE}")

    # Check Qdrant is reachable before doing anything
    try:
        if QDRANT_URL:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            target = QDRANT_URL
        else:
            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
            target = f"{QDRANT_HOST}:{QDRANT_PORT}"
        client.get_collections()
        print(f"✅ Qdrant is reachable at {target}")
    except Exception as e:
        if QDRANT_URL:
            print(f"❌ Cannot connect to Qdrant Cloud at {QDRANT_URL}")
            print(f"   Error: {e}")
            print(f"\n   Check that QDRANT_URL and QDRANT_API_KEY are set correctly.")
        else:
            print(f"❌ Cannot connect to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
            print(f"   Error: {e}")
            print(f"\n   Start local Qdrant with:")
            print(f"   docker-compose -f docker/docker-compose.yml up -d")
        sys.exit(1)

    # Build index
    print(f"\n🚀 Building index in collection: '{config.collection_name}'")
    indexer = VectorIndexer(config=config)
    stats = indexer.build(EMBEDDINGS_FILE, recreate=False)

    # Save stats
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    # Summary
    target_ui = f"{QDRANT_URL}/dashboard" if QDRANT_URL else f"http://localhost:{QDRANT_PORT}/dashboard"
    print("\n" + "=" * 55)
    print("✅  VECTOR DB POPULATED")
    print("=" * 55)
    print(f"  Collection    : {config.collection_name}")
    print(f"  Points indexed: {stats['total_indexed']}")
    print(f"  DB status     : {stats['collection']['status']}")
    print(f"\n  Dashboard     : {target_ui}")
    print("=" * 55)


if __name__ == "__main__":
    main()
