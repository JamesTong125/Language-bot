"""Private sessions send every LLM call to the private provider and never to the cloud."""

import json

from httpx import AsyncClient

from app.llm.factory import get_private_llm
from app.main import app
from tests.conftest import add_scenario, onboard, use_llm
from tests.fakes import FakeLLMClient
from tests.test_sessions_api import parse_sse

WRAPUP = json.dumps(
    {
        "went_well": "Good.",
        "recurring_mistakes": [],
        "practice": ["a", "b", "c"],
        "vocab": [],
    }
)


async def test_private_flag_is_rejected_without_a_private_provider(client: AsyncClient) -> None:
    await onboard(client)
    assert (await client.get("/scenarios")).json()["private_available"] is False
    response = await client.post(
        "/sessions", json={"scenario_id": await add_scenario(), "private": True}
    )
    assert response.status_code == 400
    assert "Private sessions" in response.json()["detail"]


async def test_every_call_in_a_private_session_uses_the_private_provider(
    client: AsyncClient,
) -> None:
    await onboard(client)
    cloud_chat, cloud_analysis = FakeLLMClient([], name="cloud"), FakeLLMClient([], name="cloud")
    private = FakeLLMClient(
        [
            "¡Hola!",  # opening
            '{"corrections": []}',  # analysis of the message
            "Muy bien.",  # reply
            '{"suggestions": ["Gracias."]}',  # hint
            WRAPUP,  # wrap-up
        ],
        name="private",
    )
    use_llm(chat=cloud_chat, analysis=cloud_analysis, private=private)
    assert (await client.get("/scenarios")).json()["private_available"] is True

    session = (
        await client.post("/sessions", json={"scenario_id": await add_scenario(), "private": True})
    ).json()
    assert session["is_private"] is True
    events = parse_sse(
        (await client.post(f"/sessions/{session['id']}/turns", json={"text": "Hola"})).text
    )
    assert [e for e, _ in events][-2:] == ["done", "corrections"]
    assert (await client.post(f"/sessions/{session['id']}/hint")).status_code == 200
    assert (await client.post(f"/sessions/{session['id']}/end")).status_code == 200

    assert len(private.calls) == 5
    assert cloud_chat.calls == [] and cloud_analysis.calls == []
    export = (await client.get("/account/export")).json()
    assert export["sessions"][0]["is_private"] is True


async def test_normal_sessions_never_use_the_private_provider(client: AsyncClient) -> None:
    await onboard(client)
    private = FakeLLMClient([], name="private")
    use_llm(chat=FakeLLMClient(["¡Hola!"]), private=private)
    session = (await client.post("/sessions", json={"scenario_id": await add_scenario()})).json()
    assert session["is_private"] is False
    assert private.calls == []


async def test_private_session_fails_closed_if_the_provider_goes_away(
    client: AsyncClient,
) -> None:
    await onboard(client)
    use_llm(chat=FakeLLMClient(["unused"]), private=FakeLLMClient(["¡Hola!"]))
    session = (
        await client.post("/sessions", json={"scenario_id": await add_scenario(), "private": True})
    ).json()
    app.dependency_overrides[get_private_llm] = lambda: None
    response = await client.post(f"/sessions/{session['id']}/turns", json={"text": "Hola"})
    assert response.status_code == 503
    assert "Private sessions" in response.json()["detail"]
