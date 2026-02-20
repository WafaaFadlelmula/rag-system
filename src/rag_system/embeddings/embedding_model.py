"""
OpenAI Embedding Model Wrapper
================================
Wraps the OpenAI embeddings API with:
  - Retry logic (rate limits / transient errors)
  - Token count validation before sending
  - Support for both single and batch requests
  - Model configuration
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI, RateLimitError, APIError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingConfig:
    # OpenAI embedding model — text-embedding-3-small is cheaper, large is better quality
    model: str = "text-embedding-3-small"

    # Max tokens the model accepts (8191 for text-embedding-3-*)
    max_tokens: int = 8191

    # Number of retries on rate limit / transient errors
    max_retries: int = 5

    # Initial backoff in seconds (doubles each retry)
    retry_backoff: float = 2.0

    # Dimensionality — None uses model default (1536 for small, 3072 for large)
    # Can reduce to e.g. 512 to save vector DB storage
    dimensions: Optional[int] = None


# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------

class EmbeddingModel:
    """
    Wraps OpenAI's embeddings endpoint.
    Usage:
        model = EmbeddingModel(api_key="sk-...")
        vector = model.embed("some text")
        vectors = model.embed_batch(["text1", "text2", ...])
    """

    def __init__(self, api_key: str, config: Optional[EmbeddingConfig] = None):
        self.cfg = config or EmbeddingConfig()
        self.client = OpenAI(api_key=api_key)
        logger.info(f"EmbeddingModel initialised: model={self.cfg.model}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """Embed a single string. Returns a float vector."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of strings in a single API call.
        Handles retries with exponential backoff on rate limit errors.
        Returns a list of float vectors in the same order as input.
        """
        if not texts:
            return []

        # Validate lengths
        for i, t in enumerate(texts):
            estimated_tokens = len(t) // 4
            if estimated_tokens > self.cfg.max_tokens:
                logger.warning(
                    f"Text at index {i} may exceed {self.cfg.max_tokens} tokens "
                    f"(estimated {estimated_tokens}). Consider reducing chunk size."
                )

        kwargs = dict(model=self.cfg.model, input=texts)
        if self.cfg.dimensions:
            kwargs["dimensions"] = self.cfg.dimensions

        attempt = 0
        backoff = self.cfg.retry_backoff

        while True:
            try:
                response = self.client.embeddings.create(**kwargs)
                # OpenAI returns items sorted by index — reorder just in case
                items = sorted(response.data, key=lambda x: x.index)
                return [item.embedding for item in items]

            except RateLimitError as e:
                attempt += 1
                if attempt > self.cfg.max_retries:
                    logger.error("Rate limit: max retries exceeded.")
                    raise
                logger.warning(f"Rate limit hit. Retrying in {backoff}s (attempt {attempt}/{self.cfg.max_retries})")
                time.sleep(backoff)
                backoff *= 2

            except APIError as e:
                attempt += 1
                if attempt > self.cfg.max_retries:
                    logger.error(f"OpenAI API error: {e}")
                    raise
                logger.warning(f"API error: {e}. Retrying in {backoff}s")
                time.sleep(backoff)
                backoff *= 2

    @property
    def model_name(self) -> str:
        return self.cfg.model

    @property
    def dimensions(self) -> Optional[int]:
        return self.cfg.dimensions