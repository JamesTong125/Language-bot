"""Phase 3 flows through the API: corrections arrive with the stream and in the transcript,
and malformed or failing analysis never breaks the chat."""

import asyncio
import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.db import get_session_factory
from app.llm.base import AllProvidersFailedError, LLMError, LLMTimeoutError
from app.llm.failover import FailoverClient
from app.models import Correction
from app.routers import sessions as sessions_router
from app.services import analysis as analysis_service
from tests.conftest import add_scenario, onboard, use_llm
from tests.fakes import FakeLLMClient
from tests.test_sessions_api import parse_sse

SOY = {
    "original": "soy 25 años",
    "corrected": "tengo 25 años",
    "error_type": "vocabulary",
    "explanation": "Spanish uses tener for age.",
    "severity": 2,
}


def corrections_json(*items: dict[str, Any]) -> str:
    return json.dumps({"corrections": list(items)}, ensure_ascii=False)


async def correction_count() -> int:
    async with get_session_factory()() as db:
        return (await db.execute(select(func.count()).select_from(Correction))).scalar_one()


async def start(client: AsyncClient, chat: Any, analysis: Any) -> int:
    await onboard(client)
    use_llm(chat=chat, analysis=analysis)
    response = await client.post("/sessions", json={"scenario_id": await add_scenario()})
    assert response.status_code == 201
    return int(response.json()["id"])


async def send(client: AsyncClient, session_id: int, text: str) -> list[tuple[str, Any]]:
    response = await client.post(f"/sessions/{session_id}/turns", json={"text": text})
    assert response.status_code == 200
    return parse_sse(response.text)


async def test_corrections_stream_after_the_reply_and_are_saved(client: AsyncClient) -> None:
    analysis = FakeLLMClient([corrections_json(SOY)])
    sid = await start(client, FakeLLMClient(["¡Hola!", "¡Qué joven!"]), analysis)

    events = await send(client, sid, "Yo soy 25 años.")
    names = [e for e, _ in events]
    assert names.index("done") < names.index("corrections")
    learner_id = events[0][1]["id"]
    payload = dict(events)["corrections"]
    assert payload["turn_id"] == learner_id
    assert payload["status"] == "ok"
    assert [
        (c["original"], c["corrected"], c["error_type"], c["severity"])
        for c in payload["corrections"]
    ] == [("soy 25 años", "tengo 25 años", "vocabulary", 2)]

    turns = (await client.get(f"/sessions/{sid}")).json()["turns"]
    learner = next(t for t in turns if t["id"] == learner_id)
    assert learner["corrections"][0]["explanation"] == "Spanish uses tener for age."
    assert all(t["corrections"] == [] for t in turns if t["role"] == "partner")


async def test_analysis_gets_the_learner_text_and_previous_partner_line(
    client: AsyncClient,
) -> None:
    analysis = FakeLLMClient(['{"corrections": []}'])
    sid = await start(client, FakeLLMClient(["¿Cuántos años tienes?", "Vale."]), analysis)
    events = await send(client, sid, "Yo soy 25 años.")
    assert dict(events)["corrections"] == {
        "turn_id": events[0][1]["id"],
        "status": "ok",
        "corrections": [],
    }
    system, user = analysis.calls[0]
    assert "Spanish" in system["content"] and "English" in system["content"]
    assert "¿Cuántos años tienes?" in user["content"]
    assert user["content"].endswith("LEARNER MESSAGE: Yo soy 25 años.")
    assert analysis.opts[0]["usage_tag"] == f"session:{sid}:analysis"


async def test_malformed_analysis_never_breaks_the_chat(client: AsyncClient) -> None:
    analysis = FakeLLMClient(["{{{", "```json\nstill broken\n```", "nope", "nope again"])
    sid = await start(client, FakeLLMClient(["¡Hola!", "Bien.", "Genial."]), analysis)
    for text in ("Yo soy 25 años.", "Y tú?"):
        events = await send(client, sid, text)
        names = [e for e, _ in events]
        assert "done" in names and "error" not in names
        assert dict(events)["corrections"]["status"] == "failed"
    assert await correction_count() == 0
    turns = (await client.get(f"/sessions/{sid}")).json()["turns"]
    assert [t["role"] for t in turns] == ["partner", "learner", "partner", "learner", "partner"]


@pytest.mark.parametrize(
    "failure",
    [AllProvidersFailedError("429"), LLMTimeoutError("slow")],
)
async def test_failing_analysis_provider_never_breaks_the_chat(
    client: AsyncClient, failure: LLMError
) -> None:
    analysis = FailoverClient([FakeLLMClient([failure])], max_retries=0)
    sid = await start(client, FakeLLMClient(["¡Hola!", "Bien."]), analysis)
    events = await send(client, sid, "Hola")
    assert "done" in [e for e, _ in events]
    assert dict(events)["corrections"]["status"] == "failed"


async def test_corrections_still_arrive_when_the_reply_fails(client: AsyncClient) -> None:
    chat = FailoverClient([FakeLLMClient(["¡Hola!", LLMTimeoutError("slow")])], max_retries=0)
    sid = await start(client, chat, FakeLLMClient([corrections_json(SOY)]))
    events = await send(client, sid, "Yo soy 25 años.")
    assert [e for e, _ in events] == ["learner_turn", "error", "corrections"]
    assert dict(events)["corrections"]["corrections"][0]["corrected"] == "tengo 25 años"


async def test_slow_analysis_closes_the_stream_but_still_saves(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_router, "ANALYSIS_WAIT_SECONDS", 0.05)
    analysis = FakeLLMClient([corrections_json(SOY)], delay=0.3)
    sid = await start(client, FakeLLMClient(["¡Hola!", "Vale."]), analysis)
    events = await send(client, sid, "Yo soy 25 años.")
    assert [e for e, _ in events][-1] == "done"
    assert "corrections" not in [e for e, _ in events]

    await asyncio.gather(*analysis_service._running)
    turns = (await client.get(f"/sessions/{sid}")).json()["turns"]
    assert turns[1]["corrections"][0]["corrected"] == "tengo 25 años"


async def test_export_and_delete_include_corrections(client: AsyncClient) -> None:
    sid = await start(
        client, FakeLLMClient(["¡Hola!", "Vale."]), FakeLLMClient([corrections_json(SOY)])
    )
    await send(client, sid, "Yo soy 25 años.")
    export = (await client.get("/account/export")).json()
    learner = export["sessions"][0]["turns"][1]
    assert learner["corrections"][0]["original"] == "soy 25 años"

    response = await client.request("DELETE", "/account", json={"password": "correct-horse-1"})
    assert response.status_code == 204
    assert await correction_count() == 0


async def test_session_reports_native_language(client: AsyncClient) -> None:
    sid = await start(client, FakeLLMClient(["¡Hola!"]), FakeLLMClient([]))
    assert (await client.get(f"/sessions/{sid}")).json()["native_language"] == "en"
