from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import get_session_factory
from app.models import LearnerProfile, User
from tests.conftest import register

PROFILE = {"native_language": "en", "target_language": "de", "cefr_level": "B2", "goals": None}


async def _count(model: type[User] | type[LearnerProfile]) -> int:
    async with get_session_factory()() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_export_contains_user_and_profiles_but_no_password(client: AsyncClient) -> None:
    await register(client)
    await client.put("/profile", json=PROFILE)
    response = await client.get("/account/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["format_version"] == 3
    assert data["user"]["email"] == "ana@example.com"
    assert data["user"]["native_language"] == "en"
    assert [p["target_language"] for p in data["learner_profiles"]] == ["de"]
    assert "argon2" not in response.text
    assert "password" not in response.text


async def test_export_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/account/export")).status_code == 401


async def test_delete_account_requires_correct_password(client: AsyncClient) -> None:
    await register(client)
    response = await client.request("DELETE", "/account", json={"password": "wrong-password"})
    assert response.status_code == 403
    assert await _count(User) == 1


async def test_delete_account_removes_user_and_related_rows(client: AsyncClient) -> None:
    await register(client, email="ana@example.com")
    await client.put("/profile", json=PROFILE)
    client.cookies.clear()
    await register(client, email="ben@example.com")
    await client.put("/profile", json=PROFILE)

    response = await client.request("DELETE", "/account", json={"password": "correct-horse-1"})
    assert response.status_code == 204
    assert await _count(User) == 1
    assert await _count(LearnerProfile) == 1
    # The cookie is cleared, and the old token no longer maps to a user.
    assert (await client.get("/profile")).status_code == 401
