"""
Qdrant Vector Store Wrapper
=============================
Handles:
  - Creating / connecting to a Qdrant collection
  - Upserting embedded chunks
  - Similarity search (returns top-k chunks + scores)
  - Metadata filtering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class QdrantConfig:
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "rag_chunks"
    vector_size: int = 1536          # must match embedding dimensions
    distance: Distance = Distance.COSINE
    # How many results to return by default
    default_top_k: int = 5


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class QdrantVectorStore:
    """
    Thin wrapper around QdrantClient for RAG operations.

    Usage:
        store = QdrantVectorStore(config)
        store.create_collection()
        store.upsert(embedded_chunks)
        results = store.search(query_vector, top_k=5)
    """

    def __init__(self, config: Optional[QdrantConfig] = None):
        self.cfg = config or QdrantConfig()
        self.client = QdrantClient(host=self.cfg.host, port=self.cfg.port)
        logger.info(f"Connected to Qdrant at {self.cfg.host}:{self.cfg.port}")

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(self, recreate: bool = False) -> None:
        """
        Create the Qdrant collection.
        If recreate=True, drops and rebuilds (useful during development).
        """
        existing = [c.name for c in self.client.get_collections().collections]

        if self.cfg.collection_name in existing:
            if recreate:
                self.client.delete_collection(self.cfg.collection_name)
                logger.info(f"Deleted existing collection: {self.cfg.collection_name}")
            else:
                logger.info(f"Collection already exists: {self.cfg.collection_name} — skipping create")
                return

        self.client.create_collection(
            collection_name=self.cfg.collection_name,
            vectors_config=VectorParams(
                size=self.cfg.vector_size,
                distance=self.cfg.distance,
            ),
        )
        logger.info(f"Created collection: {self.cfg.collection_name} "
                    f"(dim={self.cfg.vector_size}, distance={self.cfg.distance})")

    def collection_info(self) -> dict:
        """Return basic stats about the collection."""
        info = self.client.get_collection(self.cfg.collection_name)
        # points_count location changed across qdrant-client versions
        points_count = (
            getattr(info, "points_count", None)
            or getattr(info.vectors_count, "total", None)
            or "unknown"
        )
        return {
            "name": self.cfg.collection_name,
            "points_count": points_count,
            "status": str(info.status),
        }

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(self, embedded_chunks: list[dict], batch_size: int = 100) -> int:
        """
        Insert or update embedded chunks into the collection.

        Args:
            embedded_chunks: List of EmbeddedChunk dicts (from embeddings.json)
            batch_size: Points per upsert call

        Returns:
            Total number of points upserted
        """
        points = []
        for i, chunk in enumerate(embedded_chunks):
            points.append(PointStruct(
                id=i,                          # sequential int ID
                vector=chunk["embedding"],
                payload={                      # everything except the vector
                    "chunk_id":      chunk["chunk_id"],
                    "source_file":   chunk["source_file"],
                    "chunk_index":   chunk["chunk_index"],
                    "text":          chunk["text"],
                    "token_estimate": chunk["token_estimate"],
                    "headers":       chunk["headers"],
                    "chunk_type":    chunk["chunk_type"],
                    "char_start":    chunk["char_start"],
                    "char_end":      chunk["char_end"],
                    "embedding_model": chunk["embedding_model"],
                },
            ))

        # Batch upsert
        total = 0
        for start in range(0, len(points), batch_size):
            batch = points[start: start + batch_size]
            self.client.upsert(
                collection_name=self.cfg.collection_name,
                points=batch,
            )
            total += len(batch)
            logger.info(f"Upserted {total}/{len(points)} points")

        return total

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: Optional[int] = None,
        source_file: Optional[str] = None,   # filter by document
        chunk_type: Optional[str] = None,    # filter by chunk type
    ) -> list[dict]:
        """
        Similarity search. Returns top-k chunks with scores.

        Args:
            query_vector: Embedded query vector
            top_k: Number of results (default from config)
            source_file: Optional filter — only return chunks from this file
            chunk_type: Optional filter — "semantic" | "fixed_split" | "merged"

        Returns:
            List of dicts with 'score' and all chunk payload fields
        """
        top_k = top_k or self.cfg.default_top_k

        # Build optional filter
        query_filter = None
        conditions = []
        if source_file:
            conditions.append(FieldCondition(key="source_file", match=MatchValue(value=source_file)))
        if chunk_type:
            conditions.append(FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type)))
        if conditions:
            query_filter = Filter(must=conditions)

        results = self.client.query_points(
            collection_name=self.cfg.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        ).points

        return [
            {"score": round(r.score, 4), **r.payload}
            for r in results
        ]