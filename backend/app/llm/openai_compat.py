"""One LLMClient implementation for any OpenAI-compatible Chat Completions API."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import openai
from openai import AsyncOpenAI

from app.llm.base import (
    LLMError,
    LLMRateLimitedError,
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
    Message,
    SchemaT,
    Usage,
)
from app.llm.json_output import complete_json_with_retry
from app.llm.provider_config import ProviderConfig

logger = logging.getLogger(__name__)

UsageCallback = Callable[[Usage, str | None], Awaitable[None]]


def map_sdk_error(exc: Exception) -> LLMError:
    """Translate an openai SDK exception into the app's error types."""
    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeoutError(str(exc))
    if isinstance(exc, openai.RateLimitError):
        return LLMRateLimitedError(str(exc))
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500:
            return LLMUnavailableError(f"HTTP {exc.status_code}")
        return LLMRequestError(f"HTTP {exc.status_code}")
    if isinstance(exc, openai.APIConnectionError):
        return LLMUnavailableError(str(exc))
    return LLMUnavailableError(f"{type(exc).__name__}: {exc}")


class OpenAICompatibleClient:
    """Talks to a single provider. Retries and fallback live in FailoverClient."""

    def __init__(self, config: ProviderConfig, on_usage: UsageCallback | None = None) -> None:
        self.config = config
        self._on_usage = on_usage
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            max_retries=0,  # FailoverClient owns retries, with jitter.
        )

    @property
    def name(self) -> str:
        return f"{self.config.name}/{self.config.model}"

    def _request_args(self, messages: list[Message], opts: dict[str, Any]) -> dict[str, Any]:
        args: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": opts.get("max_tokens", self.config.max_tokens),
        }
        if self.config.reasoning_effort:
            args["reasoning_effort"] = self.config.reasoning_effort
        return args

    async def _record(self, prompt: int, completion: int, tag: str | None) -> None:
        if self._on_usage is None:
            return
        usage = Usage(self.config.name, self.config.model, prompt, completion)
        try:
            await self._on_usage(usage, tag)
        except Exception:  # Usage tracking must never break a reply.
            logger.exception("Failed to record LLM usage")

    async def stream_chat(self, messages: list[Message], **opts: Any) -> AsyncIterator[str]:
        tag: str | None = opts.get("usage_tag")
        timeout = self.config.timeout_seconds
        prompt_tokens = completion_tokens = 0
        try:
            stream = await self._client.chat.completions.create(
                **self._request_args(messages, opts),
                stream=True,
                stream_options={"include_usage": True},
            )
            iterator = stream.__aiter__()
            while True:
                # Time out on the gap between chunks, so a stalled stream ends cleanly.
                try:
                    async with asyncio.timeout(timeout):
                        chunk = await iterator.__anext__()
                except StopAsyncIteration:
                    break
                except TimeoutError as exc:
                    await stream.close()
                    raise LLMTimeoutError(f"No data for {timeout:.0f}s") from exc
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens or 0
                    completion_tokens = chunk.usage.completion_tokens or 0
                for choice in chunk.choices:
                    if choice.delta and choice.delta.content:
                        yield choice.delta.content
        except LLMError:
            raise
        except openai.OpenAIError as exc:
            raise map_sdk_error(exc) from exc
        finally:
            await self._record(prompt_tokens, completion_tokens, tag)

    async def complete_text(self, messages: list[Message], **opts: Any) -> str:
        args = self._request_args(messages, opts)
        if opts.get("json_mode") and self.config.json_mode:
            args["response_format"] = {"type": "json_object"}
        try:
            response = await self._client.chat.completions.create(**args)
        except openai.OpenAIError as exc:
            raise map_sdk_error(exc) from exc
        usage = response.usage
        await self._record(
            usage.prompt_tokens if usage else 0,
            usage.completion_tokens if usage else 0,
            opts.get("usage_tag"),
        )
        if not response.choices:
            return ""
        return response.choices[0].message.content or ""

    async def complete_json(
        self, messages: list[Message], schema: type[SchemaT], **opts: Any
    ) -> SchemaT:
        async def complete(msgs: list[Message]) -> str:
            return await self.complete_text(msgs, json_mode=True, **opts)

        return await complete_json_with_retry(complete, messages, schema)
