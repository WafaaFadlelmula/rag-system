"""
Hybrid Chunking Strategy for RAG System
========================================
Strategy:
  1. Split markdown by headers (## / ###) to respect semantic boundaries
  2. Merge tiny chunks (< min_chunk_tokens) with the next sibling
  3. Split oversized chunks (> max_chunk_tokens) using fixed-size + overlap

Tuned for:
  - Docling-generated markdown (## / ### headers, bullet lists, tables)
  - OpenAI text-embedding-3-* models (sweet spot: 512-1000 tokens)
"""

from __future__ import annotations

import re
import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class ChunkingConfig:
    """All tuneable parameters for the chunker."""

    # Max tokens per chunk (OpenAI embedding context is 8191; 800 is optimal for retrieval)
    max_chunk_tokens: int = 800

    # Overlap in tokens when splitting a large section into sub-chunks
    overlap_tokens: int = 150

    # Sections smaller than this get merged with the following sibling
    min_chunk_tokens: int = 100

    # Which header levels trigger a new section (1=#, 2=##, 3=###)
    split_header_levels: list[int] = field(default_factory=lambda: [1, 2, 3])

    # GPT-family tokenizer averages ~4 chars per token — used for estimates
    chars_per_token: float = 4.0

    def tokens(self, text: str) -> int:
        """Fast token count estimate (no tokenizer dependency)."""
        return max(1, int(len(text) / self.chars_per_token))

    def chars(self, n_tokens: int) -> int:
        """Convert token count back to character count."""
        return int(n_tokens * self.chars_per_token)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A single chunk ready for embedding."""
    chunk_id: str                 # unique UUID
    source_file: str              # original markdown filename (stem)
    chunk_index: int              # position in document (0-based)
    text: str                     # chunk text content
    token_estimate: int           # estimated token count
    headers: list[str]            # breadcrumb trail e.g. ["Executive Summary"]
    chunk_type: str               # "semantic" | "fixed_split" | "merged"
    char_start: int = 0           # character offset in original document
    char_end: int = 0             # character offset in original document

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Internal helper: raw section from markdown parse
# ---------------------------------------------------------------------------

@dataclass
class _Section:
    header: str
    level: int                    # 0 = no header (doc preamble)
    text: str                     # content below the header
    char_start: int = 0


# ---------------------------------------------------------------------------
# Core chunker
# ---------------------------------------------------------------------------

class HybridChunker:
    """
    Splits a markdown document into retrieval-ready chunks using a
    hybrid semantic + fixed-size strategy.
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.cfg = config or ChunkingConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_file(self, md_path: Path) -> list[Chunk]:
        """Load a markdown file and return its chunks."""
        text = md_path.read_text(encoding="utf-8")
        return self.chunk_text(text, source_file=md_path.stem)

    def chunk_text(self, markdown: str, source_file: str = "unknown") -> list[Chunk]:
        """
        Main entry point. Takes raw markdown text, returns a list of Chunk objects.
        """
        # 1. Parse into coarse sections by header
        sections = self._parse_sections(markdown)

        # 2. For each section decide: keep as-is, merge, or split further
        raw_chunks = self._process_sections(sections)

        # 3. Attach final metadata and return
        chunks: list[Chunk] = []
        for idx, (text, headers, chunk_type, char_start, char_end) in enumerate(raw_chunks):
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                source_file=source_file,
                chunk_index=idx,
                text=text.strip(),
                token_estimate=self.cfg.tokens(text),
                headers=headers,
                chunk_type=chunk_type,
                char_start=char_start,
                char_end=char_end,
            ))

        return chunks

    # ------------------------------------------------------------------
    # Step 1 — Parse markdown into sections
    # ------------------------------------------------------------------

    def _parse_sections(self, markdown: str) -> list[_Section]:
        """
        Split markdown on any header whose level is in split_header_levels.
        """
        max_level = max(self.cfg.split_header_levels)
        header_pattern = re.compile(
            r'^(#{1,' + str(max_level) + r'})\s+(.+)$',
            re.MULTILINE
        )

        sections: list[_Section] = []
        last_end = 0
        last_header = ""
        last_level = 0
        last_char_start = 0

        for match in header_pattern.finditer(markdown):
            level = len(match.group(1))
            if level not in self.cfg.split_header_levels:
                continue

            content_before = markdown[last_end:match.start()]
            if content_before.strip() or not sections:
                sections.append(_Section(
                    header=last_header,
                    level=last_level,
                    text=content_before,
                    char_start=last_char_start,
                ))

            last_header = match.group(2).strip()
            last_level = level
            last_end = match.end() + 1
            last_char_start = match.start()

        # Append the final section (after the last header)
        tail = markdown[last_end:]
        sections.append(_Section(
            header=last_header,
            level=last_level,
            text=tail,
            char_start=last_char_start,
        ))

        # Remove sections with no real text
        return [s for s in sections if s.text.strip()]

    # ------------------------------------------------------------------
    # Step 2 — Process sections: merge tiny ones, split large ones
    # ------------------------------------------------------------------

    def _process_sections(
        self, sections: list[_Section]
    ) -> list[tuple[str, list[str], str, int, int]]:
        """
        Returns list of (text, headers_breadcrumb, chunk_type, char_start, char_end).
        """
        results = []
        buffer_text = ""
        buffer_headers: list[str] = []
        buffer_start = 0
        buffer_type = "semantic"

        def flush(text, headers, ctype, cstart, cend):
            if text.strip():
                results.append((text, headers, ctype, cstart, cend))

        for i, sec in enumerate(sections):
            tok = self.cfg.tokens(sec.text)
            header_breadcrumb = [sec.header] if sec.header else []

            if tok < self.cfg.min_chunk_tokens:
                # Too small — accumulate into buffer
                if not buffer_text:
                    buffer_start = sec.char_start
                    buffer_headers = header_breadcrumb
                buffer_text += "\n\n" + sec.text
                buffer_type = "merged"

                is_last = i == len(sections) - 1
                next_large = (
                    not is_last
                    and self.cfg.tokens(sections[i + 1].text) >= self.cfg.min_chunk_tokens
                )
                if is_last or next_large:
                    flush(
                        buffer_text,
                        buffer_headers,
                        buffer_type,
                        buffer_start,
                        sec.char_start + len(sec.text),
                    )
                    buffer_text = ""
                    buffer_headers = []

            elif tok <= self.cfg.max_chunk_tokens:
                # Flush any accumulated buffer first
                if buffer_text:
                    flush(buffer_text, buffer_headers, buffer_type, buffer_start, sec.char_start)
                    buffer_text = ""
                    buffer_headers = []
                # This section fits perfectly
                flush(sec.text, header_breadcrumb, "semantic", sec.char_start, sec.char_start + len(sec.text))

            else:
                # Too large — flush buffer, then split this section
                if buffer_text:
                    flush(buffer_text, buffer_headers, buffer_type, buffer_start, sec.char_start)
                    buffer_text = ""
                    buffer_headers = []

                for sub_text, sub_start, sub_end in self._fixed_split(sec.text, sec.char_start):
                    flush(sub_text, header_breadcrumb, "fixed_split", sub_start, sub_end)

        # Final buffer flush
        if buffer_text:
            last = sections[-1]
            flush(buffer_text, buffer_headers, buffer_type, buffer_start, last.char_start + len(last.text))

        return results

    # ------------------------------------------------------------------
    # Step 3 — Fixed-size split with overlap for oversized sections
    # ------------------------------------------------------------------

    def _fixed_split(self, text: str, base_offset: int = 0) -> list[tuple[str, int, int]]:
        """
        Split text into overlapping windows of max_chunk_tokens.
        Snaps to sentence boundaries ('. ') for cleaner splits.
        Returns list of (chunk_text, char_start, char_end).
        """
        max_chars = self.cfg.chars(self.cfg.max_chunk_tokens)
        overlap_chars = self.cfg.chars(self.cfg.overlap_tokens)

        results = []
        start = 0

        while start < len(text):
            end = min(start + max_chars, len(text))

            # Snap to sentence boundary in the last 20% of the window
            if end < len(text):
                snap_zone = text[start + int(max_chars * 0.8): end]
                last_period = snap_zone.rfind('. ')
                if last_period != -1:
                    end = start + int(max_chars * 0.8) + last_period + 2

            chunk = text[start:end]
            results.append((chunk, base_offset + start, base_offset + end))

            if end >= len(text):
                break
            start = end - overlap_chars  # slide back by overlap

        return results


# ---------------------------------------------------------------------------
# Convenience: chunk all markdown files in a directory
# ---------------------------------------------------------------------------

def chunk_directory(input_dir: Path, config: Optional[ChunkingConfig] = None) -> list[Chunk]:
    """Chunk every *.md file in input_dir and return all chunks combined."""
    chunker = HybridChunker(config)
    all_chunks: list[Chunk] = []
    md_files = sorted(input_dir.glob("*.md"))

    if not md_files:
        raise FileNotFoundError(f"No .md files found in {input_dir}")

    for md_file in md_files:
        chunks = chunker.chunk_file(md_file)
        all_chunks.extend(chunks)

    return all_chunks