"""
Indexer
========
Orchestrates the full index-build pipeline:
  1. Load embeddings.json
  2. Create Qdrant collection
  3. Upsert all points
  4. Verify index health
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .store import QdrantVectorStore, QdrantConfig

logger = logging.getLogger(__name__)


class VectorIndexer:
    """
    Builds and manages the Qdrant index.

    Usage:
        indexer = VectorIndexer(store)
        indexer.build(embeddings_path, recreate=False)
        indexer.verify()
    """

    def __init__(self, store: Optional[QdrantVectorStore] = None, config: Optional[QdrantConfig] = None):
        self.store = store or QdrantVectorStore(config)

    def build(self, embeddings_path: Path, recreate: bool = False) -> dict:
        """
        Full index build from an embeddings.json file.

        Args:
            embeddings_path: Path to embeddings.json
            recreate: If True, drops and rebuilds the collection

        Returns:
            Summary stats dict
        """
        # Load embeddings
        logger.info(f"Loading embeddings from {embeddings_path}")
        with open(embeddings_path) as f:
            embedded_chunks = json.load(f)
        logger.info(f"Loaded {len(embedded_chunks)} embedded chunks")

        # Create collection
        self.store.create_collection(recreate=recreate)

        # Upsert
        total = self.store.upsert(embedded_chunks)

        # Verify
        info = self.store.collection_info()
        logger.info(f"Index built: {info}")

        return {
            "total_indexed": total,
            "collection": info,
        }

    def verify(self) -> dict:
        """Check the collection is healthy and return stats."""
        info = self.store.collection_info()
        logger.info(f"Collection health: {info}")
        return info