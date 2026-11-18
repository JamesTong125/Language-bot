"""The OpenAI-compatible client, with the SDK's network calls replaced by stubs."""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from app.llm.base import (
    LLMRateLimitedError,
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
    Usage,
)
from app.llm.openai_compat import OpenAICompatibleClient, map_sdk_error
from app.llm.provider_config import ProviderConfig
from app.schemas.conversation import HintOut

REQUEST = httpx2.Request("POST", "https://llm.example/v1/chat/completions")


def status_error(cls: type[openai.APIStatusError], code: int) -> openai.APIStatusError:
    return cls("error", response=httpx2.Response(code, request=REQUEST), body=None)


def config(**overrides: Any) -> ProviderConfig:
    values: dict[str, Any] = {
        "role": "chat",
        "base_url": "https://llm.example/v1",
        "api_key": "test-key",
        "model": "tiny-model",
        "max_tokens": 256,
        "reasoning_effort": None,
        "json_mode": False,
        "timeout_seconds": 0.2,
    }
    values.update(overrides)
    return ProviderConfig(**values)


def chunk(text: str | None = None, usage: tuple[int, int] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))] if text else [],
        usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1])
        if usage
        else None,
    )


class FakeStream:
    def __init__(self, chunks: list[SimpleNamespace], hang_after: int | None = None) -> None:
        self._chunks = chunks
        self._hang_after = hang_after
        self.closed = False

    def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        return self._gen()

    async def _gen(self) -> AsyncIterator[SimpleNamespace]:
        for i, c in enumerate(self._chunks):
            if self._hang_after is not None and i >= self._hang_after:
                await asyncio.sleep(60)
            yield c

    async def close(self) -> None:
        self.closed = True


class Recorder:
    def __init__(self) -> None:
        self.records: list[tuple[Usage, str | None]] = []

    async def __call__(self, usage: Usage, tag: str | None) -> None:
        self.records.append((usage, tag))


def stub_create(client: OpenAICompatibleClient, result: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    client._client.chat.completions.create = create  # type: ignore[method-assign]
    return calls


def test_sdk_errors_map_to_app_errors() -> None:
    assert isinstance(map_sdk_error(status_error(openai.RateLimitError, 429)), LLMRateLimitedError)
    assert isinstance(
        map_sdk_error(status_error(openai.InternalServerError, 503)), LLMUnavailableError
    )
    assert isinstance(map_sdk_error(status_error(openai.BadRequestError, 400)), LLMRequestError)
    assert isinstance(map_sdk_error(openai.APITimeoutError(request=REQUEST)), LLMTimeoutError)
    assert isinstance(
        map_sdk_error(openai.APIConnectionError(request=REQUEST)), LLMUnavailableError
    )


async def test_stream_yields_text_and_records_usage() -> None:
    recorder = Recorder()
    client = OpenAICompatibleClient(config(reasoning_effort="low"), on_usage=recorder)
    calls = stub_create(
        client, FakeStream([chunk("Hola, "), chunk("¿qué tal?"), chunk(usage=(42, 7))])
    )
    text = "".join([c async for c in client.stream_chat([], usage_tag="session:1")])
    assert text == "Hola, ¿qué tal?"
    assert calls[0]["stream"] is True
    assert calls[0]["max_tokens"] == 256
    assert calls[0]["reasoning_effort"] == "low"
    assert recorder.records == [(Usage("llm.example", "tiny-model", 42, 7), "session:1")]


async def test_stalled_stream_times_out_cleanly() -> None:
    client = OpenAICompatibleClient(config(timeout_seconds=0.05))
    stream = FakeStream([chunk("Hola"), chunk(" amigo")], hang_after=1)
    stub_create(client, stream)
    received: list[str] = []
    with pytest.raises(LLMTimeoutError):
        async for c in client.stream_chat([]):
            received.append(c)
    assert received == ["Hola"]
    assert stream.closed


async def test_rate_limit_from_sdk_surfaces_as_rate_limited() -> None:
    client = OpenAICompatibleClient(config())
    stub_create(client, status_error(openai.RateLimitError, 429))
    with pytest.raises(LLMRateLimitedError):
        async for _ in client.stream_chat([]):
            pass


async def test_complete_json_uses_native_json_mode_only_when_enabled() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"suggestions": ["Sí"]}'))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    plain = OpenAICompatibleClient(config())
    plain_calls = stub_create(plain, response)
    await plain.complete_json([], HintOut)
    assert "response_format" not in plain_calls[0]

    native = OpenAICompatibleClient(config(json_mode=True))
    native_calls = stub_create(native, response)
    await native.complete_json([], HintOut)
    assert native_calls[0]["response_format"] == {"type": "json_object"}
