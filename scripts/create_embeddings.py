"""
Script: create_embeddings.py
==============================
Run this from the project root:

    python scripts/create_embeddings.py

Reads:   data/chunks/chunks.json
Writes:  data/embeddings/embeddings.json
         data/embeddings/embedding_stats.json
         data/embeddings/checkpoint.json  (progress — safe to delete after)

Requires:
    OPENAI_API_KEY in your .env file
"""

import json
import os
import sys
import time
from pathlib import Path

# Load .env manually (no python-dotenv dependency required)
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.embeddings.embedding_model import EmbeddingConfig
from rag_system.embeddings.batch_processor import BatchEmbeddingProcessor, BatchConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT    = Path(__file__).parent.parent
CHUNKS_FILE     = PROJECT_ROOT / "data" / "chunks" / "chunks.json"
OUTPUT_DIR      = PROJECT_ROOT / "data" / "embeddings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDINGS_FILE  = OUTPUT_DIR / "embeddings.json"
STATS_FILE       = OUTPUT_DIR / "embedding_stats.json"
CHECKPOINT_FILE  = OUTPUT_DIR / "checkpoint.json"

# ---------------------------------------------------------------------------
# Configuration — tweak here
# ---------------------------------------------------------------------------
EMBEDDING_CFG = EmbeddingConfig(
    model="text-embedding-3-small",   # swap to "text-embedding-3-large" for higher quality
    max_tokens=8191,
    max_retries=5,
    retry_backoff=2.0,
    dimensions=None,                  # set e.g. 512 to reduce vector size
)

BATCH_CFG = BatchConfig(
    batch_size=100,           # chunks per API call
    delay_between_batches=0.1,  # seconds between batches
    checkpoint_every=5,       # save checkpoint every 5 batches
)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # --- API key ---
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        print("❌ OPENAI_API_KEY not set. Add it to your .env file:")
        print('   OPENAI_API_KEY="sk-..."')
        sys.exit(1)
    print(f"🔑 OpenAI API key loaded (sk-...{api_key[-4:]})")

    # --- Load chunks ---
    if not CHUNKS_FILE.exists():
        print(f"❌ Chunks file not found: {CHUNKS_FILE}")
        print("   Run `make chunk` first.")
        sys.exit(1)

    with open(CHUNKS_FILE) as f:
        chunks = json.load(f)
    print(f"📦 Loaded {len(chunks)} chunks from {CHUNKS_FILE}")

    # --- Cost estimate ---
    total_tokens = sum(c.get("token_estimate", 0) for c in chunks)
    cost_small   = (total_tokens / 1_000_000) * 0.02   # $0.02 / 1M tokens
    cost_large   = (total_tokens / 1_000_000) * 0.13   # $0.13 / 1M tokens
    print(f"\n💰 Estimated cost:")
    print(f"   Total tokens : ~{total_tokens:,}")
    print(f"   text-embedding-3-small : ~${cost_small:.4f}")
    print(f"   text-embedding-3-large : ~${cost_large:.4f}")
    print(f"\n   Using model  : {EMBEDDING_CFG.model}")

    # --- Confirm ---
    answer = input("\n▶  Proceed with embedding? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)

    # --- Embed ---
    print(f"\n🚀 Starting embedding ({len(chunks)} chunks, batch size {BATCH_CFG.batch_size})...")
    t0 = time.time()

    processor = BatchEmbeddingProcessor(
        api_key=api_key,
        embedding_config=EMBEDDING_CFG,
        batch_config=BATCH_CFG,
    )

    embedded = processor.process(chunks, checkpoint_path=CHECKPOINT_FILE)

    elapsed = time.time() - t0

    # --- Save embeddings ---
    with open(EMBEDDINGS_FILE, "w") as f:
        json.dump([e.to_dict() for e in embedded], f)
    print(f"\n💾 Saved {len(embedded)} embeddings → {EMBEDDINGS_FILE}")

    # --- Save stats ---
    sample_dim = len(embedded[0].embedding) if embedded else 0
    stats = {
        "total_embedded": len(embedded),
        "embedding_model": EMBEDDING_CFG.model,
        "vector_dimensions": sample_dim,
        "estimated_tokens": total_tokens,
        "elapsed_seconds": round(elapsed, 2),
        "chunks_per_second": round(len(embedded) / elapsed, 1) if elapsed > 0 else 0,
    }

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

    # --- Summary ---
    print("\n" + "=" * 55)
    print("✅  EMBEDDINGS COMPLETE")
    print("=" * 55)
    print(f"  Chunks embedded  : {stats['total_embedded']}")
    print(f"  Model            : {stats['embedding_model']}")
    print(f"  Vector dimensions: {stats['vector_dimensions']}")
    print(f"  Time elapsed     : {elapsed:.1f}s")
    print(f"\n  Next step → Step 4: Load into vector database")
    print("=" * 55)

    # Clean up checkpoint after successful run
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()
        print("🧹 Checkpoint file removed (run complete)")


if __name__ == "__main__":
    main()