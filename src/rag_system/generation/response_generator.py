"""
Response Generator
===================
Orchestrates the full RAG answer generation pipeline:
  1. Retrieve relevant chunks (vector + BM25 + rerank)
  2. Build context from top chunks
  3. Call LLM with context + question
  4. Return answer with sources
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Iterator

from .llm_client import LLMClient, LLMConfig, LLMResponse
from .prompts import SYSTEM_PROMPT, RAG_PROMPT_TEMPLATE, build_context
from ..embeddings.embedding_model import EmbeddingConfig
from ..vectorstore.store import QdrantConfig
from ..retrieval.retriever import VectorRetriever, RetrieverConfig
from ..retrieval.hybrid_search import HybridSearch, HybridConfig
from ..retrieval.reranker import CohereReranker, RerankerConfig

logger = logging.getLogger(__name__)


@dataclass
class RAGResponse:
    question: str
    answer: str
    sources: list[dict]             # top chunks used as context
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

    def print_pretty(self):
        print(f"\n{'='*60}")
        print(f"Q: {self.question}")
        print(f"{'='*60}")
        print(f"\n{self.answer}")
        print(f"\n--- Sources ({len(self.sources)}) ---")
        for i, s in enumerate(self.sources, 1):
            headers = " > ".join(s.get("headers", [])) or "General"
            score = s.get("rerank_score", s.get("hybrid_score", "n/a"))
            print(f"  [{i}] {s['source_file']} | {headers} | score={score}")
        print(f"\n  Tokens: {self.prompt_tokens}+{self.completion_tokens} | Cost: ${self.cost_usd:.6f}")


class ResponseGenerator:
    """
    Full RAG pipeline: retrieval → context building → LLM answer.

    Usage:
        gen = ResponseGenerator.from_config(api_key, chunks_path)
        response = gen.answer("What is the power consumption of C-PON?")
        response.print_pretty()
    """

    def __init__(
        self,
        llm_client: LLMClient,
        retriever: VectorRetriever,
        hybrid_search: HybridSearch,
        reranker: CohereReranker,
        context_chunks: int = 5,
    ):
        self.llm = llm_client
        self.retriever = retriever
        self.hybrid = hybrid_search
        self.reranker = reranker
        self.context_chunks = context_chunks

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        api_key: str,
        chunks_path: Path,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        cohere_api_key: Optional[str] = None,
        context_chunks: int = 5,
    ) -> "ResponseGenerator":
        """Convenience factory — builds the full pipeline from just an API key and chunks path.

        For Qdrant Cloud pass qdrant_url + qdrant_api_key; host/port are then ignored.
        For reranking pass cohere_api_key; if omitted, top-k hybrid results are used as-is.
        """

        # Load chunks for BM25
        with open(chunks_path) as f:
            all_chunks = json.load(f)
        logger.info(f"Loaded {len(all_chunks)} chunks for BM25")

        llm_client = LLMClient(api_key=api_key, config=LLMConfig())

        retriever = VectorRetriever(
            api_key=api_key,
            embedding_config=EmbeddingConfig(model="text-embedding-3-small"),
            qdrant_config=QdrantConfig(
                host=qdrant_host,
                port=qdrant_port,
                url=qdrant_url,
                api_key=qdrant_api_key,
            ),
            retriever_config=RetrieverConfig(top_k=20),
        )

        hybrid = HybridSearch(all_chunks, config=HybridConfig(top_k=10))
        reranker = CohereReranker(api_key=cohere_api_key, config=RerankerConfig(top_k=context_chunks))

        return cls(llm_client, retriever, hybrid, reranker, context_chunks)

    # ------------------------------------------------------------------
    # Answer (blocking)
    # ------------------------------------------------------------------

    def answer(self, question: str, top_k: int = 5) -> RAGResponse:
        """Run the full RAG pipeline and return a structured response."""

        # 1. Retrieve
        vector_results  = self.retriever.retrieve(question)
        hybrid_results  = self.hybrid.search(question, vector_results)
        final_chunks    = self.reranker.rerank(question, hybrid_results, top_k=top_k)

        # 2. Build context
        context = build_context(final_chunks, max_chunks=self.context_chunks)
        user_prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        # 3. Generate
        llm_response: LLMResponse = self.llm.complete(SYSTEM_PROMPT, user_prompt)

        return RAGResponse(
            question=question,
            answer=llm_response.answer,
            sources=final_chunks,
            model=llm_response.model,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            cost_usd=llm_response.cost_usd,
        )

    # ------------------------------------------------------------------
    # Stream answer (token by token)
    # ------------------------------------------------------------------

    def stream_answer(self, question: str, top_k: int = 5) -> tuple[Iterator[str], list[dict]]:
        """
        Stream the answer token by token.
        Returns (token_iterator, source_chunks) — sources are available immediately.
        """
        # Retrieval (non-streaming)
        vector_results = self.retriever.retrieve(question)
        hybrid_results = self.hybrid.search(question, vector_results)
        final_chunks   = self.reranker.rerank(question, hybrid_results, top_k=top_k)

        context = build_context(final_chunks, max_chunks=self.context_chunks)
        user_prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        token_stream = self.llm.stream(SYSTEM_PROMPT, user_prompt)
        return token_stream, final_chunks