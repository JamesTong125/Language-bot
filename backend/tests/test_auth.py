from httpx import AsyncClient

from app.security.cookies import COOKIE_NAME
from tests.conftest import register


async def test_register_sets_httponly_cookie(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "Ana@Example.com", "password": "correct-horse-1"}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "ana@example.com"
    set_cookie = response.headers["set-cookie"]
    assert f"{COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert set(response.json()) == {"id", "email", "native_language"}


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    await register(client)
    response = await client.post(
        "/auth/register", json={"email": "ANA@example.com", "password": "another-pass-2"}
    )
    assert response.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    response = await client.post("/auth/register", json={"email": "a@b.co", "password": "short"})
    assert response.status_code == 422


async def test_register_rejects_bad_email(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "not-an-email", "password": "long-enough-1"}
    )
    assert response.status_code == 422


async def test_login_with_correct_password(client: AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    response = await client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "correct-horse-1"}
    )
    assert response.status_code == 200
    assert COOKIE_NAME in response.cookies
    assert (await client.get("/profile")).status_code == 200


async def test_login_wrong_password_and_unknown_email_look_the_same(client: AsyncClient) -> None:
    await register(client)
    client.cookies.clear()
    wrong_password = await client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "wrong-password"}
    )
    unknown_email = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"}
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


async def test_logout_clears_cookie(client: AsyncClient) -> None:
    await register(client)
    response = await client.post("/auth/logout")
    assert response.status_code == 204
    assert (await client.get("/profile")).status_code == 401


async def test_protected_route_rejects_missing_and_forged_tokens(client: AsyncClient) -> None:
    assert (await client.get("/profile")).status_code == 401
    client.cookies.set(COOKIE_NAME, "not-a-jwt")
    assert (await client.get("/profile")).status_code == 401
