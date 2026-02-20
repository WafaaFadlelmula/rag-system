"""
Batch Processor for Embeddings
================================
Processes all chunks in configurable batches to:
  - Stay within OpenAI rate limits (TPM / RPM)
  - Show progress
  - Handle partial failures gracefully
  - Save checkpoints so you can resume if interrupted
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from .embedding_model import EmbeddingModel, EmbeddingConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedChunk:
    """A chunk enriched with its embedding vector."""
    # All original chunk fields
    chunk_id: str
    source_file: str
    chunk_index: int
    text: str
    token_estimate: int
    headers: list[str]
    chunk_type: str
    char_start: int
    char_end: int
    # New embedding fields
    embedding: list[float]
    embedding_model: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class BatchConfig:
    # Chunks per API call — OpenAI supports up to 2048 inputs per request
    # Keep at 100 to stay safe with token limits
    batch_size: int = 100

    # Seconds to wait between batches (helps avoid TPM rate limits)
    # Free tier: use 1.0+; paid tier: 0.1 is fine
    delay_between_batches: float = 0.1

    # Save progress every N batches (0 = disabled)
    checkpoint_every: int = 5


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------

class BatchEmbeddingProcessor:
    """
    Takes a list of chunk dicts (from chunks.json) and returns
    EmbeddedChunk objects with embeddings attached.

    Usage:
        processor = BatchEmbeddingProcessor(api_key="sk-...", batch_config=cfg)
        embedded = processor.process(chunks, checkpoint_path=Path("data/chunks/checkpoint.json"))
    """

    def __init__(
        self,
        api_key: str,
        embedding_config: Optional[EmbeddingConfig] = None,
        batch_config: Optional[BatchConfig] = None,
    ):
        self.model = EmbeddingModel(api_key=api_key, config=embedding_config)
        self.bcfg = batch_config or BatchConfig()

    def process(
        self,
        chunks: list[dict],
        checkpoint_path: Optional[Path] = None,
    ) -> list[EmbeddedChunk]:
        """
        Embed all chunks with batching, progress reporting, and optional checkpointing.

        Args:
            chunks: List of chunk dicts (as loaded from chunks.json)
            checkpoint_path: If provided, saves progress here so you can resume

        Returns:
            List of EmbeddedChunk objects
        """
        # Load checkpoint if it exists (resume support)
        completed_ids: set[str] = set()
        results: list[EmbeddedChunk] = []

        if checkpoint_path and checkpoint_path.exists():
            logger.info(f"Loading checkpoint from {checkpoint_path}")
            with open(checkpoint_path) as f:
                saved = json.load(f)
            results = [EmbeddedChunk(**item) for item in saved]
            completed_ids = {r.chunk_id for r in results}
            logger.info(f"Resuming from checkpoint: {len(completed_ids)} chunks already done")

        # Filter out already-completed chunks
        remaining = [c for c in chunks if c["chunk_id"] not in completed_ids]
        total = len(remaining)
        total_all = len(chunks)

        if not remaining:
            logger.info("All chunks already embedded (checkpoint complete).")
            return results

        logger.info(f"Embedding {total} chunks ({len(completed_ids)} already done from checkpoint)")

        # Split into batches
        batches = [
            remaining[i: i + self.bcfg.batch_size]
            for i in range(0, total, self.bcfg.batch_size)
        ]

        for batch_idx, batch in enumerate(batches):
            texts = [c["text"] for c in batch]
            batch_num = batch_idx + 1

            logger.info(
                f"Batch {batch_num}/{len(batches)} — "
                f"embedding {len(texts)} chunks "
                f"({batch_idx * self.bcfg.batch_size + len(texts)}/{total} total)"
            )

            try:
                vectors = self.model.embed_batch(texts)
            except Exception as e:
                logger.error(f"Batch {batch_num} failed: {e}")
                # Save checkpoint before raising so progress isn't lost
                if checkpoint_path and results:
                    self._save_checkpoint(results, checkpoint_path)
                raise

            for chunk_dict, vector in zip(batch, vectors):
                results.append(EmbeddedChunk(
                    **{k: chunk_dict[k] for k in [
                        "chunk_id", "source_file", "chunk_index", "text",
                        "token_estimate", "headers", "chunk_type", "char_start", "char_end"
                    ]},
                    embedding=vector,
                    embedding_model=self.model.model_name,
                ))

            # Checkpoint
            if (checkpoint_path
                    and self.bcfg.checkpoint_every > 0
                    and batch_num % self.bcfg.checkpoint_every == 0):
                self._save_checkpoint(results, checkpoint_path)
                logger.info(f"Checkpoint saved ({len(results)}/{total_all} chunks)")

            # Rate limit buffer
            if batch_idx < len(batches) - 1:
                time.sleep(self.bcfg.delay_between_batches)

        # Final checkpoint save
        if checkpoint_path:
            self._save_checkpoint(results, checkpoint_path)

        logger.info(f"Embedding complete: {len(results)} chunks embedded")
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _save_checkpoint(self, results: list[EmbeddedChunk], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump([r.to_dict() for r in results], f)