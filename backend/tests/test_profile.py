from typing import Any

from httpx import AsyncClient

from tests.conftest import register


def _profile(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "native_language": "en",
        "target_language": "es",
        "cefr_level": "A2",
        "goals": "Order food on holiday",
    }
    body.update(overrides)
    return body


async def test_new_user_has_no_profile(client: AsyncClient) -> None:
    await register(client)
    data = (await client.get("/profile")).json()
    assert data["email"] == "ana@example.com"
    assert data["native_language"] is None
    assert data["current"] is None
    assert data["profiles"] == []


async def test_put_profile_creates_and_returns_it(client: AsyncClient) -> None:
    await register(client)
    response = await client.put("/profile", json=_profile())
    assert response.status_code == 200
    data = response.json()
    assert data["native_language"] == "en"
    assert data["current"]["target_language"] == "es"
    assert data["current"]["cefr_level"] == "A2"
    assert data["current"]["goals"] == "Order food on holiday"
    assert (await client.get("/profile")).json() == data


async def test_put_profile_updates_existing_language(client: AsyncClient) -> None:
    await register(client)
    await client.put("/profile", json=_profile())
    data = (await client.put("/profile", json=_profile(cefr_level="B1", goals="  "))).json()
    assert len(data["profiles"]) == 1
    assert data["current"]["cefr_level"] == "B1"
    assert data["current"]["goals"] is None


async def test_switching_target_language_keeps_both_profiles(client: AsyncClient) -> None:
    await register(client)
    await client.put("/profile", json=_profile(target_language="es"))
    await client.put("/profile", json=_profile(target_language="fr", cefr_level="A1"))
    data = (await client.get("/profile")).json()
    assert [p["target_language"] for p in data["profiles"]] == ["fr", "es"]
    assert data["current"]["target_language"] == "fr"

    # Saving Spanish again makes it current.
    await client.put("/profile", json=_profile(target_language="es"))
    assert (await client.get("/profile")).json()["current"]["target_language"] == "es"


async def test_profile_validation(client: AsyncClient) -> None:
    await register(client)
    bad_bodies = [
        _profile(target_language="en"),  # same as native
        _profile(target_language="xx"),  # unsupported
        _profile(native_language="klingon"),
        _profile(cefr_level="D1"),
        _profile(goals="x" * 1001),
    ]
    for body in bad_bodies:
        assert (await client.put("/profile", json=body)).status_code == 422, body


async def test_profiles_are_private_to_each_user(client: AsyncClient) -> None:
    await register(client, email="ana@example.com")
    await client.put("/profile", json=_profile())
    client.cookies.clear()
    await register(client, email="ben@example.com")
    data = (await client.get("/profile")).json()
    assert data["email"] == "ben@example.com"
    assert data["profiles"] == []


async def test_languages_endpoint(client: AsyncClient) -> None:
    data = (await client.get("/languages")).json()
    codes = {lang["code"] for lang in data["languages"]}
    assert {"en", "es", "fr"} <= codes
    native_names = {lang["code"]: lang["native_name"] for lang in data["languages"]}
    assert native_names["fr"] == "Français"
    assert native_names["ja"] == "日本語"
    assert data["cefr_levels"] == ["A1", "A2", "B1", "B2", "C1", "C2"]
