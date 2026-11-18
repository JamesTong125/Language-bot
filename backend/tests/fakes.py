"""FakeLLMClient: a scripted LLMClient for tests. Never calls a real API."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.llm.base import LLMError, Message, SchemaT
from app.llm.json_output import complete_json_with_retry

# A script step is either reply text or an exception to raise.
Step = str | LLMError


class FakeLLMClient:
    def __init__(
        self,
        replies: Sequence[Step] = (),
        *,
        name: str = "fake",
        chunk_size: int = 4,
        fail_after_chunks: LLMError | None = None,
        delay: float = 0.0,
    ) -> None:
        self._replies = list(replies)
        self._name = name
        self._chunk_size = chunk_size
        self._fail_after_chunks = fail_after_chunks
        self._delay = delay
        self.calls: list[list[Message]] = []
        self.opts: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    def _next(self, messages: list[Message], opts: dict[str, Any]) -> str:
        self.calls.append(messages)
        self.opts.append(opts)
        if not self._replies:
            raise AssertionError(f"FakeLLMClient {self._name!r} ran out of scripted replies")
        step = self._replies.pop(0)
        if isinstance(step, LLMError):
            raise step
        return step

    async def stream_chat(self, messages: list[Message], **opts: Any) -> AsyncIterator[str]:
        text = self._next(messages, opts)
        for i in range(0, len(text), self._chunk_size):
            if self._delay:
                await asyncio.sleep(self._delay)
            yield text[i : i + self._chunk_size]
            if self._fail_after_chunks is not None:
                raise self._fail_after_chunks

    async def complete_json(
        self, messages: list[Message], schema: type[SchemaT], **opts: Any
    ) -> SchemaT:
        async def complete(msgs: list[Message]) -> str:
            return self._next(msgs, opts)

        return await complete_json_with_retry(complete, messages, schema)
