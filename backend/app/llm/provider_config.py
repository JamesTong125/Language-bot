"""Provider configurations built from env vars."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from app.config import Settings

Role = Literal["chat", "analysis", "fallback"]


@dataclass(frozen=True)
class ProviderConfig:
    role: Role
    base_url: str
    api_key: str
    model: str
    max_tokens: int
    reasoning_effort: str | None
    json_mode: bool
    timeout_seconds: float

    @property
    def name(self) -> str:
        """Provider label used in usage records, e.g. ``api.groq.com``."""
        return urlparse(self.base_url).hostname or self.base_url

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def same_endpoint(self, other: "ProviderConfig") -> bool:
        return (self.base_url.rstrip("/"), self.model) == (other.base_url.rstrip("/"), other.model)


def provider_config(settings: Settings, role: Role) -> ProviderConfig:
    return ProviderConfig(
        role=role,
        base_url=getattr(settings, f"llm_{role}_base_url"),
        api_key=getattr(settings, f"llm_{role}_api_key"),
        model=getattr(settings, f"llm_{role}_model"),
        max_tokens=getattr(settings, f"llm_{role}_max_tokens"),
        reasoning_effort=getattr(settings, f"llm_{role}_reasoning_effort") or None,
        json_mode=getattr(settings, f"llm_{role}_json_mode"),
        timeout_seconds=settings.llm_timeout_seconds,
    )
