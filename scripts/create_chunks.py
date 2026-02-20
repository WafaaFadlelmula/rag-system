"""
Script: create_chunks.py
========================
Run this from the project root:

    python scripts/create_chunks.py

Reads:   data/processed/markdown/*.md
Writes:  data/chunks/chunks.json
         data/chunks/chunking_stats.json
"""

import json
import sys
from pathlib import Path
from collections import Counter

# Make sure src/ is on the path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_system.ingestion.chunker import HybridChunker, ChunkingConfig, chunk_directory

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR    = PROJECT_ROOT / "data" / "processed" / "markdown"
OUTPUT_DIR   = PROJECT_ROOT / "data" / "chunks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHUNKS_FILE = OUTPUT_DIR / "chunks.json"
STATS_FILE  = OUTPUT_DIR / "chunking_stats.json"

# ---------------------------------------------------------------------------
# Config — tweak here if needed
# ---------------------------------------------------------------------------
config = ChunkingConfig(
    max_chunk_tokens=800,
    overlap_tokens=150,
    min_chunk_tokens=100,
    split_header_levels=[1, 2, 3],
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
def main():
    print(f"📂 Reading markdown files from: {INPUT_DIR}")
    md_files = sorted(INPUT_DIR.glob("*.md"))
    if not md_files:
        print("❌ No .md files found. Make sure Step 1 (ingestion) ran successfully.")
        sys.exit(1)

    print(f"   Found {len(md_files)} files: {[f.name for f in md_files]}")

    chunker = HybridChunker(config)
    all_chunks = []

    per_file_stats = []
    for md_file in md_files:
        chunks = chunker.chunk_file(md_file)
        all_chunks.extend(chunks)

        token_sizes = [c.token_estimate for c in chunks]
        type_counts = Counter(c.chunk_type for c in chunks)
        per_file_stats.append({
            "file": md_file.name,
            "num_chunks": len(chunks),
            "avg_tokens": round(sum(token_sizes) / len(token_sizes), 1) if token_sizes else 0,
            "min_tokens": min(token_sizes) if token_sizes else 0,
            "max_tokens": max(token_sizes) if token_sizes else 0,
            "chunk_types": dict(type_counts),
        })
        print(f"   ✅ {md_file.name}: {len(chunks)} chunks "
              f"(avg {per_file_stats[-1]['avg_tokens']} tokens)")

    # ------------------------------------------------------------------
    # Save chunks
    # ------------------------------------------------------------------
    chunks_data = [c.to_dict() for c in all_chunks]
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved {len(all_chunks)} chunks → {CHUNKS_FILE}")

    # ------------------------------------------------------------------
    # Save stats
    # ------------------------------------------------------------------
    all_tokens = [c.token_estimate for c in all_chunks]
    all_types  = Counter(c.chunk_type for c in all_chunks)

    stats = {
        "total_chunks": len(all_chunks),
        "total_files": len(md_files),
        "overall": {
            "avg_tokens": round(sum(all_tokens) / len(all_tokens), 1) if all_tokens else 0,
            "min_tokens": min(all_tokens) if all_tokens else 0,
            "max_tokens": max(all_tokens) if all_tokens else 0,
            "chunk_types": dict(all_types),
        },
        "config": {
            "max_chunk_tokens": config.max_chunk_tokens,
            "overlap_tokens": config.overlap_tokens,
            "min_chunk_tokens": config.min_chunk_tokens,
            "split_header_levels": config.split_header_levels,
        },
        "per_file": per_file_stats,
    }

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(f"📊 Stats saved → {STATS_FILE}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 55)
    print("✅  CHUNKING COMPLETE")
    print("=" * 55)
    print(f"  Total chunks   : {stats['total_chunks']}")
    print(f"  Avg tokens     : {stats['overall']['avg_tokens']}")
    print(f"  Token range    : {stats['overall']['min_tokens']} – {stats['overall']['max_tokens']}")
    print(f"  Chunk types    : {stats['overall']['chunk_types']}")
    print(f"\n  Next step → Step 3: Generate embeddings with OpenAI")
    print("=" * 55)


if __name__ == "__main__":
    main()