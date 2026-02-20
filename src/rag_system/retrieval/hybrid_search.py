"""
Hybrid Search: Vector + BM25 + Reciprocal Rank Fusion
=======================================================
Combines:
  1. Vector search results (semantic similarity)
  2. BM25 keyword search results (exact term matching)
  3. RRF (Reciprocal Rank Fusion) to merge both ranked lists

RRF formula: score(d) = sum(1 / (k + rank(d)))
where k=60 is a smoothing constant that reduces the impact of high rankings.

This is especially good for technical documents with specific terms
like "C-PON", "DT15", "OLM" that vector search may miss.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


@dataclass
class HybridConfig:
    # Number of final results to return after fusion
    top_k: int = 10

    # RRF smoothing constant (60 is standard)
    rrf_k: int = 60

    # Weight for vector results vs BM25 (1.0 = equal weight)
    vector_weight: float = 1.0
    bm25_weight: float = 1.0


class HybridSearch:
    """
    Combines vector search results with BM25 keyword search using
    Reciprocal Rank Fusion to produce a unified ranked result list.

    Usage:
        hs = HybridSearch(all_chunks, config)
        results = hs.search(query, vector_results)
    """

    def __init__(self, all_chunks: list[dict], config: Optional[HybridConfig] = None):
        self.cfg = config or HybridConfig()
        self.chunks = all_chunks
        self._build_bm25_index(all_chunks)

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _build_bm25_index(self, chunks: list[dict]) -> None:
        """Tokenise all chunk texts and build a BM25 index."""
        logger.info(f"Building BM25 index over {len(chunks)} chunks...")
        tokenised = [self._tokenise(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(tokenised)
        logger.info("BM25 index ready")

    def _tokenise(self, text: str) -> list[str]:
        """Simple whitespace + lowercase tokeniser."""
        return text.lower().split()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, vector_results: list[dict]) -> list[dict]:
        """
        Perform hybrid search by fusing vector results with BM25.

        Args:
            query: Original user query string
            vector_results: Results from VectorRetriever.retrieve()

        Returns:
            Re-ranked list of chunk dicts with 'hybrid_score' added
        """
        # --- BM25 search ---
        tokens = self._tokenise(query)
        bm25_scores = self.bm25.get_scores(tokens)

        # Get top BM25 results (same pool size as vector)
        pool_size = max(len(vector_results), self.cfg.top_k * 2)
        bm25_top_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[:pool_size]

        bm25_results = [
            {**self.chunks[i], "bm25_score": float(bm25_scores[i])}
            for i in bm25_top_indices
            if bm25_scores[i] > 0
        ]

        logger.info(f"BM25 returned {len(bm25_results)} results for query: '{query[:60]}'")

        # --- Reciprocal Rank Fusion ---
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)
        return fused[: self.cfg.top_k]

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
    ) -> list[dict]:
        """
        Merge two ranked lists using RRF.
        Each result is identified by chunk_id.
        """
        k = self.cfg.rrf_k
        rrf_scores: dict[str, float] = {}
        chunk_map: dict[str, dict] = {}

        # Score from vector ranking
        for rank, chunk in enumerate(vector_results):
            cid = chunk["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + self.cfg.vector_weight * (1.0 / (k + rank + 1))
            chunk_map[cid] = chunk

        # Score from BM25 ranking
        for rank, chunk in enumerate(bm25_results):
            cid = chunk["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + self.cfg.bm25_weight * (1.0 / (k + rank + 1))
            if cid not in chunk_map:
                chunk_map[cid] = chunk

        # Sort by fused score
        sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

        results = []
        for cid in sorted_ids:
            chunk = dict(chunk_map[cid])
            chunk["hybrid_score"] = round(rrf_scores[cid], 6)
            results.append(chunk)

        return results