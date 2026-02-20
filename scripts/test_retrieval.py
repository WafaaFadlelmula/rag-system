"""
Script: test_retrieval.py
==========================
Tests the full retrieval pipeline end-to-end:
  Vector search → BM25 + RRF fusion → Cross-encoder reranking

Run from project root:
    python scripts/test_retrieval.py

Requires:
    - Qdrant running (make vectordb-up)
    - OPENAI_API_KEY in .env
    - uv add rank-bm25 sentence-transformers
"""

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# Load .env
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.embeddings.embedding_model import EmbeddingConfig
from rag_system.vectorstore.store import QdrantConfig
from rag_system.retrieval.retriever import VectorRetriever, RetrieverConfig
from rag_system.retrieval.hybrid_search import HybridSearch, HybridConfig
from rag_system.retrieval.reranker import CrossEncoderReranker, RerankerConfig

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT    = Path(__file__).parent.parent
CHUNKS_FILE     = PROJECT_ROOT / "data" / "chunks" / "chunks.json"

API_KEY = os.environ.get("OPENAI_API_KEY", "")

EMBEDDING_CFG = EmbeddingConfig(model="text-embedding-3-small")
QDRANT_CFG    = QdrantConfig(host="localhost", port=6333, collection_name="rag_chunks")
RETRIEVER_CFG = RetrieverConfig(top_k=20)      # fetch 20 candidates for reranker
HYBRID_CFG    = HybridConfig(top_k=10)         # fuse down to 10
RERANKER_CFG  = RerankerConfig(top_k=5)        # rerank to final 5

# ---------------------------------------------------------------------------
# Test queries — adjust to your documents
# ---------------------------------------------------------------------------
TEST_QUERIES = [
    "What are the C-PON test results?",
    "What is the power consumption of the C-PON system?",
    "What AR/VR applications were tested in the field trial?",
    "What were the key milestones achieved in Q3 2023?",
]

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not API_KEY:
        print("❌ OPENAI_API_KEY not set in .env"); sys.exit(1)

    # Load all chunks for BM25
    with open(CHUNKS_FILE) as f:
        all_chunks = json.load(f)
    print(f"📦 Loaded {len(all_chunks)} chunks for BM25 index\n")

    # Initialise pipeline components
    retriever = VectorRetriever(
        api_key=API_KEY,
        embedding_config=EMBEDDING_CFG,
        qdrant_config=QDRANT_CFG,
        retriever_config=RETRIEVER_CFG,
    )
    hybrid    = HybridSearch(all_chunks, config=HYBRID_CFG)
    reranker  = CrossEncoderReranker(config=RERANKER_CFG)

    # Run test queries
    for query in TEST_QUERIES:
        print("=" * 60)
        print(f"🔍 Query: {query}")
        print("=" * 60)

        # Step 1: Vector search
        vector_results = retriever.retrieve(query)
        print(f"  Vector search    : {len(vector_results)} results")

        # Step 2: Hybrid (BM25 + RRF)
        hybrid_results = hybrid.search(query, vector_results)
        print(f"  After hybrid/RRF : {len(hybrid_results)} results")

        # Step 3: Rerank
        final_results = reranker.rerank(query, hybrid_results)
        print(f"  After reranking  : {len(final_results)} results\n")

        # Display top 3
        for i, r in enumerate(final_results[:3], 1):
            print(f"  [{i}] score={r['rerank_score']:+.3f} | {r['source_file']} | {r['headers']}")
            print(f"      {r['text'][:150].strip()}...")
            print()

    print("✅ Retrieval test complete")


if __name__ == "__main__":
    main()