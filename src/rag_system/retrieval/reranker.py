"""
Cross-Encoder Reranker
========================
Uses a sentence-transformers cross-encoder to rerank hybrid search results.

Cross-encoders are more accurate than bi-encoders for relevance scoring
because they see the query AND the document together, not separately.

Model used: cross-encoder/ms-marco-MiniLM-L-6-v2
  - Fast, small (~80MB), runs on CPU
  - Trained on MS MARCO passage ranking
  - Returns a relevance score (higher = more relevant)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RerankerConfig:
    # Hugging Face cross-encoder model
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Final number of results to return after reranking
    top_k: int = 5

    # Max character length of text sent to reranker (avoids slow inference on huge chunks)
    max_text_length: int = 512


class CrossEncoderReranker:
    """
    Reranks a list of candidate chunks using a cross-encoder model.
    Downloads the model on first use (~80MB, cached to ~/.cache/huggingface/).

    Usage:
        reranker = CrossEncoderReranker()
        results = reranker.rerank(query, candidates)
    """

    def __init__(self, config: Optional[RerankerConfig] = None):
        self.cfg = config or RerankerConfig()
        self._model = None   # lazy load on first use

    def _load_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading cross-encoder: {self.cfg.model_name}")
                self._model = CrossEncoder(self.cfg.model_name)
                logger.info("Cross-encoder loaded")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for reranking.\n"
                    "Install with: uv add sentence-transformers"
                )

    def rerank(self, query: str, candidates: list[dict], top_k: int = None) -> list[dict]:
        """
        Rerank candidate chunks by relevance to the query.

        Args:
            query: Original user query
            candidates: List of chunk dicts (from hybrid search or vector search)
            top_k: Override default top_k from config

        Returns:
            Top-k chunks sorted by reranker score (highest first),
            with 'rerank_score' field added
        """
        if not candidates:
            return []

        k = top_k if top_k is not None else self.cfg.top_k
        self._load_model()

        # Prepare (query, passage) pairs for the cross-encoder
        pairs = [
            (query, c["text"][: self.cfg.max_text_length])
            for c in candidates
        ]

        logger.info(f"Reranking {len(pairs)} candidates...")
        scores = self._model.predict(pairs)

        # Attach scores and sort
        scored = []
        for chunk, score in zip(candidates, scores):
            c = dict(chunk)
            c["rerank_score"] = round(float(score), 4)
            scored.append(c)

        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        top = scored[:k]

        logger.info(
            f"Reranking complete. Top score: {top[0]['rerank_score']:.4f}, "
            f"Bottom score: {top[-1]['rerank_score']:.4f}"
        )
        return top