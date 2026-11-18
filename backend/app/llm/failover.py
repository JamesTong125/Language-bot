"""Retries with exponential backoff and jitter, then fallback to the next provider."""

import asyncio
import logging
import random
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any

from app.llm.base import (
    RETRYABLE_ERRORS,
    AllProvidersFailedError,
    LLMClient,
    LLMError,
    LLMNotConfiguredError,
    LLMOutputInvalidError,
    LLMTimeoutError,
    Message,
    SchemaT,
)

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    """Full jitter: a random delay up to base * 2^attempt, capped."""
    return random.uniform(0, min(cap, base * 2**attempt))


class FailoverClient:
    """An LLMClient over an ordered list of providers.

    For each provider, retryable errors (429, 5xx, connection) are retried ``max_retries``
    times with backoff. A timeout or a rejected request moves straight to the next provider.
    When every provider fails, AllProvidersFailedError is raised.
    """

    def __init__(
        self,
        providers: Sequence[LLMClient],
        max_retries: int = 2,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._providers = list(providers)
        self._max_retries = max_retries
        self._sleep = sleep

    @property
    def name(self) -> str:
        return " -> ".join(p.name for p in self._providers) or "(none)"

    def _require_providers(self) -> None:
        if not self._providers:
            raise LLMNotConfiguredError("No LLM provider is configured")

    async def stream_chat(self, messages: list[Message], **opts: Any) -> AsyncIterator[str]:
        self._require_providers()
        last_error: LLMError | None = None
        for index, provider in enumerate(self._providers):
            attempt = 0
            while True:
                started = False
                try:
                    async for chunk in provider.stream_chat(messages, **opts):
                        started = True
                        yield chunk
                    return
                except LLMError as exc:
                    if started:
                        # Text already reached the client; switching provider would garble it.
                        raise
                    last_error = exc
                    if isinstance(exc, RETRYABLE_ERRORS) and attempt < self._max_retries:
                        await self._sleep(backoff_delay(attempt))
                        attempt += 1
                        continue
                    self._log_giving_up(provider, exc, index)
                    break
        raise AllProvidersFailedError(str(last_error)) from last_error

    async def complete_json(
        self, messages: list[Message], schema: type[SchemaT], **opts: Any
    ) -> SchemaT:
        self._require_providers()
        last_error: LLMError | None = None
        for index, provider in enumerate(self._providers):
            attempt = 0
            while True:
                try:
                    return await provider.complete_json(messages, schema, **opts)
                except LLMOutputInvalidError:
                    # The provider answered; its output was bad twice. Don't burn more quota.
                    raise
                except LLMError as exc:
                    last_error = exc
                    if isinstance(exc, RETRYABLE_ERRORS) and attempt < self._max_retries:
                        await self._sleep(backoff_delay(attempt))
                        attempt += 1
                        continue
                    self._log_giving_up(provider, exc, index)
                    break
        raise AllProvidersFailedError(str(last_error)) from last_error

    def _log_giving_up(self, provider: LLMClient, exc: LLMError, index: int) -> None:
        has_next = index + 1 < len(self._providers)
        kind = "timed out" if isinstance(exc, LLMTimeoutError) else type(exc).__name__
        logger.warning(
            "LLM provider %s failed (%s)%s",
            provider.name,
            kind,
            ", switching to fallback" if has_next else "",
        )
