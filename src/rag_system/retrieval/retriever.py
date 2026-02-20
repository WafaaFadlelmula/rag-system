"""
Vector Retriever
=================
Embeds a query with OpenAI and retrieves top-k similar chunks from Qdrant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ..embeddings.embedding_model import EmbeddingModel, EmbeddingConfig
from ..vectorstore.store import QdrantVectorStore, QdrantConfig

logger = logging.getLogger(__name__)


@dataclass
class RetrieverConfig:
    top_k: int = 20                  # fetch more than needed — reranker will trim
    source_file: Optional[str] = None  # optional filter by document
    score_threshold: float = 0.0     # minimum similarity score (0-1)


class VectorRetriever:
    """
    Embeds a query and retrieves the most similar chunks from Qdrant.
    Returns more results than needed so the reranker has candidates to work with.
    """

    def __init__(
        self,
        api_key: str,
        embedding_config: Optional[EmbeddingConfig] = None,
        qdrant_config: Optional[QdrantConfig] = None,
        retriever_config: Optional[RetrieverConfig] = None,
    ):
        self.embedding_model = EmbeddingModel(api_key=api_key, config=embedding_config)
        self.store = QdrantVectorStore(config=qdrant_config)
        self.cfg = retriever_config or RetrieverConfig()

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """
        Embed query and return top-k similar chunks.

        Args:
            query: Natural language question
            top_k: Override default top_k

        Returns:
            List of chunk dicts with 'score' field added
        """
        k = top_k or self.cfg.top_k
        logger.info(f"Vector search: query='{query[:60]}...' top_k={k}")

        query_vector = self.embedding_model.embed(query)
        results = self.store.search(
            query_vector=query_vector,
            top_k=k,
            source_file=self.cfg.source_file,
        )

        # Apply score threshold
        if self.cfg.score_threshold > 0:
            results = [r for r in results if r["score"] >= self.cfg.score_threshold]

        logger.info(f"Vector search returned {len(results)} results")
        return results