"""The provider-neutral LLM interface used by the rest of the app."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class Usage:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class LLMClient(Protocol):
    """Every LLM call in the app goes through this interface.

    Options accepted by implementations (all optional):
    - ``usage_tag``: a label such as ``"session:12"`` used when logging token usage.
    - ``max_tokens``: override the configured output token cap for this call.
    """

    @property
    def name(self) -> str: ...

    def stream_chat(self, messages: list[Message], **opts: Any) -> AsyncIterator[str]:
        """Yield the reply text in chunks as the provider streams it."""
        ...

    async def complete_json(
        self, messages: list[Message], schema: type[SchemaT], **opts: Any
    ) -> SchemaT:
        """Return the reply parsed as JSON and validated against ``schema``."""
        ...


# --- Errors ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base class for every LLM failure."""


class LLMNotConfiguredError(LLMError):
    """No provider has an API key and base URL."""


class LLMRateLimitedError(LLMError):
    """HTTP 429. Retryable."""


class LLMUnavailableError(LLMError):
    """HTTP 5xx or a connection failure. Retryable."""


class LLMTimeoutError(LLMError):
    """The request, or a gap between streamed chunks, took too long."""


class LLMRequestError(LLMError):
    """The provider rejected the request (4xx other than 429). Not retryable."""


class LLMOutputInvalidError(LLMError):
    """The model's JSON output failed validation, even after one retry."""


class AllProvidersFailedError(LLMError):
    """Every configured provider failed for this request."""

    user_message = "The daily limit has been reached. Please try again later."


RETRYABLE_ERRORS: tuple[type[LLMError], ...] = (LLMRateLimitedError, LLMUnavailableError)
