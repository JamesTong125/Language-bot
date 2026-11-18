"""Main conversation flows through the HTTP API, with the LLM mocked."""

import json
from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import get_session_factory
from app.llm.base import LLMRateLimitedError, LLMTimeoutError
from app.llm.failover import FailoverClient
from app.models import PracticeSession, Turn
from tests.conftest import add_scenario, onboard, register, use_llm
from tests.fakes import FakeLLMClient


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def count(model: type[PracticeSession] | type[Turn]) -> int:
    async with get_session_factory()() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def start(client: AsyncClient, scenario_id: int) -> dict[str, Any]:
    response = await client.post("/sessions", json={"scenario_id": scenario_id})
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_scenarios_need_onboarding(client: AsyncClient) -> None:
    await register(client)
    assert (await client.get("/scenarios")).status_code == 409


async def test_scenarios_show_built_ins_and_matching_custom_ones(client: AsyncClient) -> None:
    await onboard(client, target="es")
    builtin = await add_scenario(title="Built-in")
    await add_scenario(title="French only", target_language="fr")
    await add_scenario(title="Spanish only", target_language="es", cefr_level="B2")
    titles = [s["title"] for s in (await client.get("/scenarios")).json()["scenarios"]]
    assert titles == ["Built-in", "Spanish only"]
    assert builtin


async def test_start_session_returns_opening_message(client: AsyncClient) -> None:
    await onboard(client, target="es", level="A2")
    chat = FakeLLMClient(["¡Hola! ¿Qué le pongo?"])
    use_llm(chat=chat)
    session = await start(client, await add_scenario())
    assert session["target_language"] == "es"
    assert session["cefr_level"] == "A2"
    assert [(t["role"], t["text"]) for t in session["turns"]] == [
        ("partner", "¡Hola! ¿Qué le pongo?")
    ]
    system = chat.calls[0][0]["content"]
    assert "Spanish" in system and "A2" in system and "A friendly barista." in system


async def test_start_session_llm_failure_saves_nothing(client: AsyncClient) -> None:
    await onboard(client)
    use_llm(chat=FailoverClient([FakeLLMClient([LLMRateLimitedError("429")])], max_retries=0))
    response = await client.post("/sessions", json={"scenario_id": await add_scenario()})
    assert response.status_code == 503
    assert "daily limit" in response.json()["detail"].lower()
    assert await count(PracticeSession) == 0


async def test_start_session_rejects_hidden_scenarios(client: AsyncClient) -> None:
    await onboard(client, target="es")
    french = await add_scenario(target_language="fr")
    assert (await client.post("/sessions", json={"scenario_id": french})).status_code == 404
    assert (await client.post("/sessions", json={"scenario_id": 99999})).status_code == 404


async def test_multi_turn_conversation_streams_and_saves(client: AsyncClient) -> None:
    await onboard(client)
    chat = FakeLLMClient(["¡Hola!", "Claro, un café con leche.", "Son dos euros."])
    use_llm(chat=chat)
    session = await start(client, await add_scenario())

    for text in ("Un café, por favor.", "¿Cuánto es?"):
        response = await client.post(f"/sessions/{session['id']}/turns", json={"text": text})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = parse_sse(response.text)
        assert events[0][0] == "learner_turn" and events[0][1]["text"] == text
        assert {e for e, _ in events[1:-1]} == {"token"}
        assert events[-1][0] == "done"
        streamed = "".join(d["text"] for e, d in events if e == "token")
        assert streamed == events[-1][1]["text"]

    transcript = (await client.get(f"/sessions/{session['id']}")).json()["turns"]
    assert [t["role"] for t in transcript] == [
        "partner",
        "learner",
        "partner",
        "learner",
        "partner",
    ]
    assert transcript[-1]["text"] == "Son dos euros."
    # The last call saw the whole conversation, ending with the newest learner message.
    last_call = chat.calls[-1]
    assert last_call[-1] == {"role": "user", "content": "¿Cuánto es?"}
    assert chat.opts[-1]["usage_tag"] == f"session:{session['id']}"


async def test_failed_reply_keeps_transcript_and_can_be_retried(client: AsyncClient) -> None:
    await onboard(client)
    chat = FakeLLMClient(["¡Hola!", LLMTimeoutError("slow"), "Perfecto."])
    use_llm(chat=FailoverClient([chat], max_retries=0))
    session = await start(client, await add_scenario())
    url = f"/sessions/{session['id']}/turns"

    events = parse_sse((await client.post(url, json={"text": "Un té, por favor."})).text)
    assert [e for e, _ in events] == ["learner_turn", "error"]
    assert events[-1][1]["retryable"] is True
    transcript = (await client.get(f"/sessions/{session['id']}")).json()["turns"]
    assert [t["role"] for t in transcript] == ["partner", "learner"]

    events = parse_sse((await client.post(url, json={"retry": True})).text)
    assert events[0][0] == "token" and events[-1][0] == "done"
    transcript = (await client.get(f"/sessions/{session['id']}")).json()["turns"]
    assert [t["text"] for t in transcript] == ["¡Hola!", "Un té, por favor.", "Perfecto."]


async def test_retry_needs_a_waiting_learner_message(client: AsyncClient) -> None:
    await onboard(client)
    use_llm(chat=FakeLLMClient(["¡Hola!"]))
    session = await start(client, await add_scenario())
    response = await client.post(f"/sessions/{session['id']}/turns", json={"retry": True})
    assert response.status_code == 409


async def test_turn_validation(client: AsyncClient) -> None:
    await onboard(client)
    use_llm(chat=FakeLLMClient(["¡Hola!"]))
    session = await start(client, await add_scenario())
    url = f"/sessions/{session['id']}/turns"
    for body in ({"text": "   "}, {"text": "x" * 1001}, {}, {"text": "hola", "retry": True}):
        assert (await client.post(url, json=body)).status_code == 422, body
    assert await count(Turn) == 1


async def test_sessions_are_private(client: AsyncClient) -> None:
    await onboard(client, email="ana@example.com")
    use_llm(chat=FakeLLMClient(["¡Hola!"]))
    session = await start(client, await add_scenario())
    client.cookies.clear()
    await onboard(client, email="ben@example.com")
    assert (await client.get(f"/sessions/{session['id']}")).status_code == 404
    response = await client.post(f"/sessions/{session['id']}/turns", json={"text": "hola"})
    assert response.status_code == 404
    assert (await client.post(f"/sessions/{session['id']}/hint")).status_code == 404


async def test_hint_returns_suggestions_from_analysis_model(client: AsyncClient) -> None:
    await onboard(client)
    analysis = FakeLLMClient(
        ['```json\n{"suggestions": ["Un café, por favor.", "¿Tiene té?"]}\n```']
    )
    use_llm(chat=FakeLLMClient(["¡Hola! ¿Qué desea?"]), analysis=analysis)
    session = await start(client, await add_scenario())
    response = await client.post(f"/sessions/{session['id']}/hint")
    assert response.status_code == 200
    assert response.json() == {"suggestions": ["Un café, por favor.", "¿Tiene té?"]}
    assert "PARTNER: ¡Hola! ¿Qué desea?" in analysis.calls[0][-1]["content"]
    assert await count(Turn) == 1  # Hints are not stored as turns.


async def test_malformed_hint_output_never_breaks_the_chat(client: AsyncClient) -> None:
    await onboard(client)
    chat = FakeLLMClient(["¡Hola!", "Muy bien."])
    use_llm(chat=chat, analysis=FakeLLMClient(["not json", "{still not json"]))
    session = await start(client, await add_scenario())
    response = await client.post(f"/sessions/{session['id']}/hint")
    assert response.status_code == 503
    events = parse_sse(
        (await client.post(f"/sessions/{session['id']}/turns", json={"text": "Hola"})).text
    )
    assert events[-1][0] == "done"


async def test_export_and_delete_cover_sessions(client: AsyncClient) -> None:
    await onboard(client)
    use_llm(chat=FakeLLMClient(["¡Hola!", "Vale."]))
    session = await start(client, await add_scenario())
    await client.post(f"/sessions/{session['id']}/turns", json={"text": "Un café."})

    export = (await client.get("/account/export")).json()
    assert [t["text"] for t in export["sessions"][0]["turns"]] == ["¡Hola!", "Un café.", "Vale."]
    assert export["sessions"][0]["scenario_title"] == "Ordering at a café"

    response = await client.request("DELETE", "/account", json={"password": "correct-horse-1"})
    assert response.status_code == 204
    assert await count(PracticeSession) == 0
    assert await count(Turn) == 0
