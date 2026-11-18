"""Test setup: a fresh schema in a separate PostgreSQL database, truncated between tests."""

import os

# Configure before any app module reads settings.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://immersion:immersion@db:5432/immersion_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")
os.environ.setdefault("CORS_ORIGIN", "http://localhost:3000")

from collections.abc import AsyncIterator, Iterator  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine, get_session_factory  # noqa: E402
from app.llm.base import LLMClient  # noqa: E402
from app.llm.factory import get_analysis_llm, get_chat_llm  # noqa: E402
from app.llm.failover import FailoverClient  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Scenario  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _schema() -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with get_engine().begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _no_real_llm() -> Iterator[None]:
    """Tests must never reach a real provider. Tests that need an LLM override these."""
    app.dependency_overrides[get_chat_llm] = lambda: FailoverClient([])
    app.dependency_overrides[get_analysis_llm] = lambda: FailoverClient([])
    yield
    app.dependency_overrides.clear()


def use_llm(chat: LLMClient | None = None, analysis: LLMClient | None = None) -> None:
    if chat is not None:
        app.dependency_overrides[get_chat_llm] = lambda: chat
    if analysis is not None:
        app.dependency_overrides[get_analysis_llm] = lambda: analysis


async def add_scenario(**overrides: Any) -> int:
    values: dict[str, Any] = {
        "title": "Ordering at a café",
        "description": "A busy café.",
        "partner_persona": "A friendly barista.",
        "goal": "Order a drink and pay.",
        "target_language": None,
        "cefr_level": "A1",
        "is_custom": False,
        "created_by": None,
    }
    values.update(overrides)
    async with get_session_factory()() as db:
        scenario = Scenario(**values)
        db.add(scenario)
        await db.commit()
        return scenario.id


async def onboard(
    client: AsyncClient, email: str = "ana@example.com", target: str = "es", level: str = "A1"
) -> None:
    await register(client, email=email)
    response = await client.put(
        "/profile",
        json={"native_language": "en", "target_language": target, "cefr_level": level},
    )
    assert response.status_code == 200, response.text


async def register(
    client: AsyncClient, email: str = "ana@example.com", password: str = "correct-horse-1"
) -> None:
    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
