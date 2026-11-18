import logging

import pytest
from httpx import AsyncClient

from app.db import get_session_factory
from app.llm.base import Usage
from app.llm.usage import UsageRecorder
from tests.conftest import register


async def test_usage_accumulates_per_provider_model_and_day(client: AsyncClient) -> None:
    recorder = UsageRecorder(get_session_factory(), daily_budget=None)
    await recorder(Usage("api.groq.com", "small", 100, 20), "session:1")
    await recorder(Usage("api.groq.com", "small", 50, 10), "session:1")
    await recorder(Usage("generativelanguage.googleapis.com", "flash", 300, 40), "session:1")

    await register(client)
    report = (await client.get("/debug/llm-usage")).json()
    assert report["requests_today"] == 3
    rows = {(r["provider"], r["model"]): r for r in report["rows"]}
    groq = rows[("api.groq.com", "small")]
    assert (groq["requests"], groq["prompt_tokens"], groq["completion_tokens"]) == (2, 150, 30)
    assert rows[("generativelanguage.googleapis.com", "flash")]["requests"] == 1


async def test_budget_warning_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    recorder = UsageRecorder(get_session_factory(), daily_budget=2)
    with caplog.at_level(logging.WARNING):
        await recorder(Usage("p", "m", 1, 1), None)
        await recorder(Usage("p", "m", 1, 1), None)
    assert "budget exceeded: 2 of 2" in caplog.text


async def test_usage_endpoint_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/debug/llm-usage")).status_code == 401
