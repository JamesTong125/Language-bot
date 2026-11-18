"""The deck, the review queue, and ratings through the API."""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.db import get_session_factory
from app.models import LearnerProfile, Review, VocabItem
from app.srs.scheduler import SrsState, schedule
from tests.conftest import onboard


async def profile_id(email: str = "ana@example.com") -> int:
    from app.models import User

    async with get_session_factory()() as db:
        q = select(LearnerProfile.id).join(User).where(User.email == email)
        return int((await db.execute(q)).scalars().first() or 0)


async def add_card(pid: int, term: str, *, due_in_days: float = 0, **extra: Any) -> int:
    values: dict[str, Any] = {
        "learner_profile_id": pid,
        "term": term,
        "translation": f"<{term}>",
        "example_sentence": None,
        "ease": 2.5,
        "interval_days": 0,
        "repetitions": 0,
        "due_at": datetime.now(UTC) + timedelta(days=due_in_days),
    }
    values.update(extra)
    async with get_session_factory()() as db:
        card = VocabItem(**values)
        db.add(card)
        await db.commit()
        return card.id


async def test_review_queue_is_due_cards_oldest_first(client: AsyncClient) -> None:
    await onboard(client)
    pid = await profile_id()
    await add_card(pid, "mañana", due_in_days=1)  # not due
    await add_card(pid, "ayer", due_in_days=-3)
    await add_card(pid, "hoy", due_in_days=-0.01)
    await add_card(pid, "anteayer", due_in_days=-5)
    queue = (await client.get("/vocab/review")).json()
    assert [i["term"] for i in queue["items"]] == ["anteayer", "ayer", "hoy"]
    assert queue["due_count"] == 3
    assert [i["term"] for i in (await client.get("/vocab/review?limit=2")).json()["items"]] == [
        "anteayer",
        "ayer",
    ]


async def test_rating_updates_schedule_as_the_scheduler_specifies(client: AsyncClient) -> None:
    await onboard(client)
    pid = await profile_id()
    card_id = await add_card(pid, "la cuenta", due_in_days=-1)

    expected = SrsState(2.5, 0, 0, datetime.now(UTC))
    for rating in (4, 4, 5, 1):
        before = datetime.now(UTC)
        response = await client.post(f"/vocab/{card_id}/review", json={"rating": rating})
        assert response.status_code == 200
        item = response.json()["item"]
        expected = schedule(expected, rating, before)
        assert (item["repetitions"], item["interval_days"]) == (
            expected.repetitions,
            expected.interval_days,
        )
        assert item["ease"] == expected.ease
        due = datetime.fromisoformat(item["due_at"])
        assert abs(due - (before + timedelta(days=expected.interval_days))) < timedelta(seconds=5)

    # 4 -> 1 day, 4 -> 6 days, 5 -> 16 days, then a lapse back to 1 day.
    assert (item["interval_days"], item["repetitions"]) == (1, 0)
    async with get_session_factory()() as db:
        ratings = (await db.execute(select(Review.rating).order_by(Review.id))).scalars().all()
    assert list(ratings) == [4, 4, 5, 1]


async def test_reviewed_card_leaves_the_queue(client: AsyncClient) -> None:
    await onboard(client)
    card_id = await add_card(await profile_id(), "el pan", due_in_days=-1)
    await client.post(f"/vocab/{card_id}/review", json={"rating": 3})
    assert (await client.get("/vocab/review")).json() == {"items": [], "due_count": 0}


async def test_invalid_ratings_are_rejected(client: AsyncClient) -> None:
    await onboard(client)
    card_id = await add_card(await profile_id(), "el pan")
    for body in ({"rating": -1}, {"rating": 6}, {"rating": "good"}, {}):
        assert (await client.post(f"/vocab/{card_id}/review", json=body)).status_code == 422


async def test_deck_filters_search_and_pagination(client: AsyncClient) -> None:
    await onboard(client)
    pid = await profile_id()
    for i in range(25):
        await add_card(pid, f"palabra {i:02d}", due_in_days=1)
    await add_card(pid, "el 100% café", due_in_days=-1)
    await add_card(pid, "la cuenta", due_in_days=2, repetitions=2, translation="the bill")

    first = (await client.get("/vocab?page_size=10")).json()
    assert first["total"] == 27 and len(first["items"]) == 10 and first["due_count"] == 1
    assert first["items"][0]["term"] == "la cuenta"  # newest first
    third = (await client.get("/vocab?page_size=10&page=3")).json()
    assert len(third["items"]) == 7

    def terms(data: dict[str, Any]) -> list[str]:
        return [i["term"] for i in data["items"]]

    assert terms((await client.get("/vocab?filter=due")).json()) == ["el 100% café"]
    assert terms((await client.get("/vocab?filter=learning")).json()) == ["la cuenta"]
    assert (await client.get("/vocab?filter=new")).json()["total"] == 26
    assert terms((await client.get("/vocab?q=BILL")).json()) == ["la cuenta"]
    # Wildcards are escaped: "%" matches only a literal percent sign.
    assert terms((await client.get("/vocab?q=%25")).json()) == ["el 100% café"]
    assert (await client.get("/vocab?filter=bogus")).status_code == 422


async def test_delete_card(client: AsyncClient) -> None:
    await onboard(client)
    card_id = await add_card(await profile_id(), "el pan")
    assert (await client.delete(f"/vocab/{card_id}")).status_code == 204
    assert (await client.get("/vocab")).json()["total"] == 0
    assert (await client.delete(f"/vocab/{card_id}")).status_code == 404


async def test_cards_are_private(client: AsyncClient) -> None:
    await onboard(client, email="ana@example.com")
    card_id = await add_card(await profile_id("ana@example.com"), "el pan", due_in_days=-1)
    client.cookies.clear()
    await onboard(client, email="ben@example.com")
    assert (await client.get("/vocab")).json()["total"] == 0
    assert (await client.get("/vocab/review")).json()["items"] == []
    assert (await client.post(f"/vocab/{card_id}/review", json={"rating": 5})).status_code == 404
    assert (await client.delete(f"/vocab/{card_id}")).status_code == 404


async def test_deck_only_shows_the_current_language(client: AsyncClient) -> None:
    await onboard(client, target="es")
    await add_card(await profile_id(), "el pan")
    await client.put(
        "/profile", json={"native_language": "en", "target_language": "fr", "cefr_level": "A1"}
    )
    assert (await client.get("/vocab")).json()["total"] == 0


async def test_export_and_delete_include_vocab_and_reviews(client: AsyncClient) -> None:
    await onboard(client)
    card_id = await add_card(await profile_id(), "el pan", due_in_days=-1)
    await client.post(f"/vocab/{card_id}/review", json={"rating": 4})
    export = (await client.get("/account/export")).json()
    assert export["vocab_items"][0]["term"] == "el pan"
    assert [r["rating"] for r in export["vocab_items"][0]["reviews"]] == [4]

    await client.request("DELETE", "/account", json={"password": "correct-horse-1"})
    async with get_session_factory()() as db:
        assert (await db.execute(select(VocabItem))).first() is None
        assert (await db.execute(select(Review))).first() is None
