"""
LLM Client — OpenAI gpt-4o-mini
=================================
Wraps the OpenAI chat completions API with:
  - Retry logic
  - Streaming support
  - Token usage tracking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Iterator

from openai import OpenAI, RateLimitError, APIError

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.1        # low = more factual, less creative
    max_tokens: int = 1024
    max_retries: int = 3
    retry_backoff: float = 2.0


@dataclass
class LLMResponse:
    answer: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float                 # estimated cost

    def __str__(self):
        return self.answer


class LLMClient:
    """
    OpenAI chat completions client.

    Usage:
        client = LLMClient(api_key="sk-...")
        response = client.complete(system_prompt, user_prompt)
        print(response.answer)
    """

    # gpt-4o-mini pricing (per 1M tokens, as of 2024)
    COST_PER_1M_INPUT  = 0.15
    COST_PER_1M_OUTPUT = 0.60

    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        self.cfg = config or LLMConfig()
        self.client = OpenAI(api_key=api_key)
        logger.info(f"LLMClient initialised: model={self.cfg.model}")

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        Send a chat completion request and return the response.
        Retries on rate limit / transient errors.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

        attempt = 0
        backoff = self.cfg.retry_backoff

        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.cfg.model,
                    messages=messages,
                    temperature=self.cfg.temperature,
                    max_tokens=self.cfg.max_tokens,
                )

                usage = response.usage
                cost = (
                    (usage.prompt_tokens     / 1_000_000) * self.COST_PER_1M_INPUT +
                    (usage.completion_tokens / 1_000_000) * self.COST_PER_1M_OUTPUT
                )

                return LLMResponse(
                    answer=response.choices[0].message.content.strip(),
                    model=response.model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    cost_usd=round(cost, 6),
                )

            except RateLimitError:
                attempt += 1
                if attempt > self.cfg.max_retries:
                    raise
                logger.warning(f"Rate limit. Retrying in {backoff}s ({attempt}/{self.cfg.max_retries})")
                time.sleep(backoff)
                backoff *= 2

            except APIError as e:
                attempt += 1
                if attempt > self.cfg.max_retries:
                    raise
                logger.warning(f"API error: {e}. Retrying in {backoff}s")
                time.sleep(backoff)
                backoff *= 2

    def stream(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """
        Stream a chat completion token by token.
        Yields text chunks as they arrive.

        Usage:
            for token in client.stream(sys_prompt, user_prompt):
                print(token, end="", flush=True)
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]

        with self.client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            stream=True,
        ) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta