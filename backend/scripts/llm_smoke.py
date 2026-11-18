"""Manual smoke test against the real providers in your env. Not part of the test suite.

    docker compose exec api python -m scripts.llm_smoke [model ...]

Streams one short reply from each configured provider (or from each model given on the
command line, using the chat provider's URL and key) and prints timing. Keys are never printed.
"""

import asyncio
import sys
import time
from dataclasses import replace

from app.config import get_settings
from app.llm.base import LLMError, Message
from app.llm.openai_compat import OpenAICompatibleClient
from app.llm.provider_config import ProviderConfig, provider_config

MESSAGES: list[Message] = [
    {"role": "system", "content": "Reply only in Spanish, in one short sentence."},
    {"role": "user", "content": "Hello, I would like a coffee."},
]


async def check(config: ProviderConfig) -> None:
    client = OpenAICompatibleClient(config)
    start = time.monotonic()
    first: float | None = None
    parts: list[str] = []
    try:
        async for chunk in client.stream_chat(MESSAGES):
            first = first or time.monotonic() - start
            parts.append(chunk)
        total = time.monotonic() - start
        print(f"OK   {config.role:9} {client.name}: first token {first:.1f}s, total {total:.1f}s")
        print(f"     {''.join(parts).strip()!r}")
    except LLMError as exc:
        print(f"FAIL {config.role:9} {client.name}: {type(exc).__name__}: {str(exc)[:160]}")


async def main(models: list[str]) -> None:
    settings = get_settings()
    if models:
        base = provider_config(settings, "chat")
        configs = [replace(base, model=m) for m in models]
    else:
        configs = [provider_config(settings, r) for r in ("chat", "analysis", "fallback")]
    for config in configs:
        if config.is_configured:
            await check(config)
        else:
            print(f"SKIP {config.role:9} (not configured)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
