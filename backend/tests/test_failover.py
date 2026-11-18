import pytest

from app.llm.base import (
    AllProvidersFailedError,
    LLMNotConfiguredError,
    LLMOutputInvalidError,
    LLMRateLimitedError,
    LLMRequestError,
    LLMTimeoutError,
    LLMUnavailableError,
    Message,
)
from app.llm.failover import FailoverClient, backoff_delay
from app.schemas.conversation import HintOut
from tests.fakes import FakeLLMClient

MESSAGES: list[Message] = [{"role": "user", "content": "Hola"}]
HINT = '{"suggestions": ["Hola"]}'


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


async def collect(client: FailoverClient) -> str:
    return "".join([c async for c in client.stream_chat(MESSAGES)])


def test_backoff_grows_and_is_capped() -> None:
    for attempt in range(10):
        delay = backoff_delay(attempt, base=0.5, cap=8.0)
        assert 0 <= delay <= min(8.0, 0.5 * 2**attempt)


async def test_rate_limit_is_retried_with_backoff_then_succeeds() -> None:
    primary = FakeLLMClient([LLMRateLimitedError("429"), LLMUnavailableError("503"), "¡Hola!"])
    sleeps = Sleeps()
    client = FailoverClient([primary], max_retries=2, sleep=sleeps)
    assert await collect(client) == "¡Hola!"
    assert len(sleeps.delays) == 2


async def test_rate_limit_exhausts_retries_then_uses_fallback() -> None:
    primary = FakeLLMClient([LLMRateLimitedError("429")] * 3, name="primary")
    fallback = FakeLLMClient(["Hola desde el respaldo"], name="fallback")
    client = FailoverClient([primary, fallback], max_retries=2, sleep=Sleeps())
    assert await collect(client) == "Hola desde el respaldo"
    assert len(primary.calls) == 3
    assert len(fallback.calls) == 1


async def test_every_provider_rate_limited_raises_friendly_error() -> None:
    primary = FakeLLMClient([LLMRateLimitedError("429")] * 3)
    fallback = FakeLLMClient([LLMRateLimitedError("429")] * 3)
    client = FailoverClient([primary, fallback], max_retries=2, sleep=Sleeps())
    with pytest.raises(AllProvidersFailedError) as info:
        await collect(client)
    assert "daily limit" in info.value.user_message.lower()


async def test_timeout_switches_to_fallback_without_retrying() -> None:
    primary = FakeLLMClient([LLMTimeoutError("slow"), "unused"])
    fallback = FakeLLMClient(["Hola"])
    sleeps = Sleeps()
    client = FailoverClient([primary, fallback], max_retries=2, sleep=sleeps)
    assert await collect(client) == "Hola"
    assert len(primary.calls) == 1
    assert sleeps.delays == []


async def test_rejected_request_is_not_retried() -> None:
    primary = FakeLLMClient([LLMRequestError("400")])
    client = FailoverClient([primary], max_retries=2, sleep=Sleeps())
    with pytest.raises(AllProvidersFailedError):
        await collect(client)
    assert len(primary.calls) == 1


async def test_failure_after_text_started_is_not_retried() -> None:
    primary = FakeLLMClient(["Hola amigo"], fail_after_chunks=LLMUnavailableError("reset"))
    fallback = FakeLLMClient(["unused"])
    client = FailoverClient([primary, fallback], sleep=Sleeps())
    received: list[str] = []
    with pytest.raises(LLMUnavailableError):
        async for chunk in client.stream_chat(MESSAGES):
            received.append(chunk)
    assert received == ["Hola"]
    assert fallback.calls == []


async def test_complete_json_falls_back_on_rate_limit() -> None:
    primary = FakeLLMClient([LLMRateLimitedError("429")])
    fallback = FakeLLMClient([HINT])
    client = FailoverClient([primary, fallback], max_retries=0, sleep=Sleeps())
    assert (await client.complete_json(MESSAGES, HintOut)).suggestions == ["Hola"]


async def test_complete_json_invalid_output_does_not_fall_back() -> None:
    primary = FakeLLMClient(["nope", "still nope"])
    fallback = FakeLLMClient([HINT])
    client = FailoverClient([primary, fallback], sleep=Sleeps())
    with pytest.raises(LLMOutputInvalidError):
        await client.complete_json(MESSAGES, HintOut)
    assert fallback.calls == []


async def test_no_providers_means_not_configured() -> None:
    with pytest.raises(LLMNotConfiguredError):
        await collect(FailoverClient([]))
