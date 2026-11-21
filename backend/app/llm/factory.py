"""Builds the LLM clients from env vars. Use these as FastAPI dependencies."""

from functools import lru_cache

from app.config import get_settings
from app.db import get_session_factory
from app.llm.base import LLMClient
from app.llm.failover import FailoverClient
from app.llm.openai_compat import OpenAICompatibleClient
from app.llm.provider_config import ProviderConfig, Role, provider_config
from app.llm.usage import UsageRecorder


def _build(*roles: Role) -> FailoverClient:
    settings = get_settings()
    recorder = UsageRecorder(get_session_factory(), settings.llm_daily_request_budget)
    configs: list[ProviderConfig] = []
    for role in roles:
        config = provider_config(settings, role)
        if config.is_configured and not any(config.same_endpoint(c) for c in configs):
            configs.append(config)
    providers = [OpenAICompatibleClient(c, on_usage=recorder) for c in configs]
    return FailoverClient(providers, max_retries=settings.llm_max_retries)


@lru_cache
def get_chat_llm() -> LLMClient:
    """The conversation partner: chat provider, then fallback."""
    return _build("chat", "fallback")


@lru_cache
def get_analysis_llm() -> LLMClient:
    """Analysis, wrap-up, and hints: analysis provider, then fallback."""
    return _build("analysis", "fallback")


@lru_cache
def get_private_llm() -> LLMClient | None:
    """The private provider for private sessions, with no fallback. None if not configured."""
    client = _build("private")
    return client if client.has_providers else None
