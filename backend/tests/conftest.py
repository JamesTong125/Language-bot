"""Test setup: a fresh schema in a separate PostgreSQL database, truncated between tests."""

import os

# Configure before any app module reads settings.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://immersion:immersion@db:5432/immersion_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-signing")
os.environ.setdefault("CORS_ORIGIN", "http://localhost:3000")

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


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


async def register(
    client: AsyncClient, email: str = "ana@example.com", password: str = "correct-horse-1"
) -> None:
    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
