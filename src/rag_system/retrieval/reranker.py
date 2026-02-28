"""
Cohere Reranker
================
Uses the Cohere Rerank API to rerank hybrid search results.

Replaces the local cross-encoder (sentence-transformers / PyTorch) to cut
memory usage from ~600 MB to ~120 MB — making it viable on Render's free
512 MB tier.

Cohere free tier: 1,000 rerank calls/month.
Model: rerank-v3.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RerankerConfig:
    model: str = "rerank-v3.5"
    top_k: int = 5
    max_text_length: int = 512


class CohereReranker:
    """
    Reranks candidates using the Cohere Rerank API.
    Falls back to returning top-k hybrid results unchanged if no API key is set.

    Usage:
        reranker = CohereReranker(api_key="...")
        results = reranker.rerank(query, candidates)
    """

    def __init__(self, api_key: Optional[str], config: Optional[RerankerConfig] = None):
        self.cfg = config or RerankerConfig()
        self._client = None
        if api_key:
            import cohere
            self._client = cohere.Client(api_key=api_key)
            logger.info("Cohere reranker initialised")
        else:
            logger.warning("COHERE_API_KEY not set — reranking will be skipped")

    def rerank(self, query: str, candidates: list[dict], top_k: int = None) -> list[dict]:
        """
        Rerank candidate chunks by relevance to the query.

        Args:
            query: Original user query
            candidates: List of chunk dicts (from hybrid search)
            top_k: Override default top_k from config

        Returns:
            Top-k chunks sorted by reranker score (highest first),
            with 'rerank_score' field added
        """
        if not candidates:
            return []

        k = top_k if top_k is not None else self.cfg.top_k

        if self._client is None:
            # No API key — return top-k from hybrid results as-is
            for c in candidates:
                c.setdefault("rerank_score", round(float(c.get("hybrid_score", 0.0)), 4))
            return candidates[:k]

        docs = [c["text"][: self.cfg.max_text_length] for c in candidates]
        logger.info(f"Reranking {len(docs)} candidates via Cohere API...")

        response = self._client.rerank(
            model=self.cfg.model,
            query=query,
            documents=docs,
            top_n=k,
        )

        ranked = []
        for r in response.results:
            c = dict(candidates[r.index])
            c["rerank_score"] = round(r.relevance_score, 4)
            ranked.append(c)

        logger.info(
            f"Reranking complete. Top score: {ranked[0]['rerank_score']:.4f}, "
            f"Bottom score: {ranked[-1]['rerank_score']:.4f}"
        )
        return ranked
