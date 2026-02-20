"""
Script: populate_vectordb.py
==============================
Run from project root:

    python scripts/populate_vectordb.py

Reads:   data/embeddings/embeddings.json
Writes:  Qdrant collection (persisted to data/qdrant/)

Requires:
    Qdrant running in Docker:
        docker-compose -f docker/docker-compose.yml up -d
"""

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.vectorstore.store import QdrantConfig
from rag_system.vectorstore.indexer import VectorIndexer

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT    = Path(__file__).parent.parent
EMBEDDINGS_FILE = PROJECT_ROOT / "data" / "embeddings" / "embeddings.json"
STATS_FILE      = PROJECT_ROOT / "data" / "embeddings" / "vectordb_stats.json"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
config = QdrantConfig(
    host="localhost",
    port=6333,
    collection_name="rag_chunks",
    vector_size=1536,       # must match your embedding dimensions
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
        from qdrant_client import QdrantClient
        client = QdrantClient(host=config.host, port=config.port)
        client.get_collections()
        print(f"✅ Qdrant is running at {config.host}:{config.port}")
    except Exception as e:
        print(f"❌ Cannot connect to Qdrant at {config.host}:{config.port}")
        print(f"   Error: {e}")
        print(f"\n   Start Qdrant with:")
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
    print("\n" + "=" * 55)
    print("✅  VECTOR DB POPULATED")
    print("=" * 55)
    print(f"  Collection   : {config.collection_name}")
    print(f"  Points indexed: {stats['total_indexed']}")
    print(f"  DB status    : {stats['collection']['status']}")
    print(f"\n  Qdrant UI    : http://localhost:6333/dashboard")
    print(f"\n  Next step → Step 5: Build the retrieval system")
    print("=" * 55)


if __name__ == "__main__":
    main()