import json

from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import get_session_factory
from app.models import Turn
from tests.conftest import add_scenario, onboard, use_llm, use_settings
from tests.fakes import FakeLLMClient

DRAFT = json.dumps(
    {
        "refused": False,
        "title": "At the bakery",
        "description": "You're buying bread for a picnic.",
        "partner_persona": "A cheerful baker.",
        "goal": "Buy two loaves and ask what's fresh today.",
    }
)


async def learner_turns() -> int:
    async with get_session_factory()() as db:
        q = select(func.count()).select_from(Turn).where(Turn.role == "learner")
        return int((await db.execute(q)).scalar_one())


async def test_turns_per_minute(client: AsyncClient) -> None:
    use_settings(rate_limit_turns_per_minute=2)
    await onboard(client)
    use_llm(
        chat=FakeLLMClient(["¡Hola!", "Uno.", "Dos."]),
        analysis=FakeLLMClient(['{"corrections": []}'] * 2),
    )
    sid = (await client.post("/sessions", json={"scenario_id": await add_scenario()})).json()["id"]
    url = f"/sessions/{sid}/turns"
    assert (await client.post(url, json={"text": "uno"})).status_code == 200
    assert (await client.post(url, json={"text": "dos"})).status_code == 200

    response = await client.post(url, json={"text": "tres"})
    assert response.status_code == 429
    assert "quickly" in response.json()["detail"]
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert await learner_turns() == 2  # the limited message wasn't saved


async def test_sessions_per_day(client: AsyncClient) -> None:
    use_settings(rate_limit_sessions_per_day=1)
    await onboard(client)
    use_llm(chat=FakeLLMClient(["¡Hola!", "¡Hola otra vez!"]))
    scenario = await add_scenario()
    assert (await client.post("/sessions", json={"scenario_id": scenario})).status_code == 201
    response = await client.post("/sessions", json={"scenario_id": scenario})
    assert response.status_code == 429
    assert "daily limit" in response.json()["detail"]
    assert int(response.headers["retry-after"]) > 3600


async def test_scenarios_per_day(client: AsyncClient) -> None:
    use_settings(rate_limit_scenarios_per_day=1)
    await onboard(client)
    use_llm(analysis=FakeLLMClient([DRAFT, DRAFT]))
    body = {"description": "buying bread at a bakery"}
    assert (await client.post("/scenarios", json=body)).status_code == 201
    assert (await client.post("/scenarios", json=body)).status_code == 429


async def test_limits_are_per_user(client: AsyncClient) -> None:
    use_settings(rate_limit_sessions_per_day=1)
    use_llm(chat=FakeLLMClient(["¡Hola!", "¡Hola!"]))
    scenario = await add_scenario()
    await onboard(client, email="ana@example.com")
    assert (await client.post("/sessions", json={"scenario_id": scenario})).status_code == 201
    client.cookies.clear()
    await onboard(client, email="ben@example.com")
    assert (await client.post("/sessions", json={"scenario_id": scenario})).status_code == 201


async def test_zero_disables_a_limit(client: AsyncClient) -> None:
    use_settings(rate_limit_sessions_per_day=0)
    await onboard(client)
    use_llm(chat=FakeLLMClient(["¡Hola!"] * 3))
    scenario = await add_scenario()
    for _ in range(3):
        assert (await client.post("/sessions", json={"scenario_id": scenario})).status_code == 201
