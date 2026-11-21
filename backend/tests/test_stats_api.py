"""GET /stats with data seeded straight into the database at chosen times."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy import Date, cast, func, select

from app.db import get_session_factory
from app.models import (
    Correction,
    LearnerProfile,
    PracticeSession,
    Review,
    Turn,
    User,
    VocabItem,
)
from tests.conftest import add_scenario, onboard

NOW = datetime.now(UTC)


async def profile_id(email: str = "ana@example.com") -> int:
    async with get_session_factory()() as db:
        q = (
            select(LearnerProfile.id)
            .join(User)
            .where(User.email == email)
            .order_by(LearnerProfile.updated_at.desc())
        )
        return int((await db.execute(q)).scalars().first() or 0)


async def seed_session(
    pid: int,
    scenario_id: int,
    *,
    at: datetime,
    learner_turns: int = 3,
    mistakes: list[str] | None = None,
    level: str = "A2",
    ended: bool = True,
) -> int:
    """A session with alternating turns. ``mistakes`` lists error types on the first turn."""
    mistakes = mistakes or []
    async with get_session_factory()() as db:
        session = PracticeSession(
            learner_profile_id=pid,
            scenario_id=scenario_id,
            cefr_level=level,
            started_at=at,
            ended_at=at + timedelta(minutes=10) if ended else None,
        )
        db.add(session)
        await db.flush()
        first_learner: Turn | None = None
        for i in range(learner_turns):
            db.add(Turn(session_id=session.id, role="partner", text="¿Y?", created_at=at))
            turn = Turn(session_id=session.id, role="learner", text=f"msg {i}", created_at=at)
            db.add(turn)
            first_learner = first_learner or turn
        await db.flush()
        for error_type in mistakes:
            assert first_learner is not None
            db.add(
                Correction(
                    turn_id=first_learner.id,
                    original="x",
                    corrected="y",
                    error_type=error_type,
                    explanation="z",
                    severity=2,
                )
            )
        if ended and learner_turns:
            rate = Decimal(1 if mistakes else 0) / Decimal(learner_turns)
            session.error_rate = rate.quantize(Decimal("0.0001"))
        await db.commit()
        return session.id


async def stats(client: AsyncClient, tz: str = "UTC") -> dict[str, Any]:
    response = await client.get(f"/stats?tz={tz}")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_new_learner_gets_empty_stats(client: AsyncClient) -> None:
    await onboard(client, level="A2")
    data = await stats(client)
    assert data["streak"] == {"days": 0, "practised_today": False}
    assert data["totals"] == {
        "sessions_completed": 0,
        "learner_messages": 0,
        "vocab_items": 0,
        "vocab_due": 0,
        "reviews": 0,
    }
    assert len(data["sessions_per_week"]) == 8
    assert all(w["sessions"] == 0 for w in data["sessions_per_week"])
    assert data["error_rate_trend"] == [] and data["error_types"] == []
    assert data["level"]["current_level"] == "A2"
    assert data["level"]["direction"] is None
    assert data["level"]["sessions_counted"] == 0


async def test_streak_counts_messages_and_reviews_on_consecutive_days(
    client: AsyncClient,
) -> None:
    await onboard(client)
    pid, sid = await profile_id(), await add_scenario()
    await seed_session(pid, sid, at=NOW)
    await seed_session(pid, sid, at=NOW - timedelta(days=1))
    async with get_session_factory()() as db:  # a review two days ago continues the streak
        card = VocabItem(
            learner_profile_id=pid,
            term="pan",
            translation="bread",
            ease=2.5,
            interval_days=1,
            repetitions=1,
            due_at=NOW,
        )
        db.add(card)
        await db.flush()
        db.add(Review(vocab_item_id=card.id, rating=4, reviewed_at=NOW - timedelta(days=2)))
        await db.commit()
    await seed_session(pid, sid, at=NOW - timedelta(days=4))  # after a gap: not counted
    data = await stats(client)
    assert data["streak"] == {"days": 3, "practised_today": True}
    assert data["totals"]["reviews"] == 1
    assert data["totals"]["vocab_due"] == 1


async def test_local_dates_follow_the_time_zone() -> None:
    utc = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
    async with get_session_factory()() as db:
        tokyo = (await db.execute(select(cast(func.timezone("Asia/Tokyo", utc), Date)))).scalar()
        la = (
            await db.execute(select(cast(func.timezone("America/Los_Angeles", utc), Date)))
        ).scalar()
    assert str(tokyo) == "2026-03-11"
    assert str(la) == "2026-03-10"


async def test_unknown_time_zone_falls_back_to_utc(client: AsyncClient) -> None:
    await onboard(client)
    assert (await stats(client, tz="Mars/Olympus_Mons"))["time_zone"] == "UTC"
    assert (await stats(client, tz="Europe/Madrid"))["time_zone"] == "Europe/Madrid"


async def test_sessions_trend_and_error_types(client: AsyncClient) -> None:
    await onboard(client, level="A2")
    pid, sid = await profile_id(), await add_scenario(title="Café")
    for days_ago, mistakes in [(20, ["grammar", "grammar"]), (10, ["vocabulary"]), (0, [])]:
        await seed_session(pid, sid, at=NOW - timedelta(days=days_ago), mistakes=mistakes)
    await seed_session(pid, sid, at=NOW, ended=False)  # open sessions count as started
    data = await stats(client)

    assert sum(w["sessions"] for w in data["sessions_per_week"]) == 4
    assert data["sessions_per_week"][-1]["sessions"] >= 2
    trend = data["error_rate_trend"]
    assert [round(p["error_rate"], 4) for p in trend] == [0.3333, 0.3333, 0.0]  # oldest first
    assert trend[0]["scenario_title"] == "Café" and trend[0]["cefr_level"] == "A2"
    assert data["error_types"] == [
        {"error_type": "grammar", "count": 2},
        {"error_type": "vocabulary", "count": 1},
    ]
    assert data["totals"]["sessions_completed"] == 3
    assert data["totals"]["learner_messages"] == 12


async def test_low_error_rate_suggests_moving_up(client: AsyncClient) -> None:
    await onboard(client, level="A2")
    pid, sid = await profile_id(), await add_scenario()
    for days_ago in (3, 2, 1):
        await seed_session(pid, sid, at=NOW - timedelta(days=days_ago))
    await seed_session(pid, sid, at=NOW, learner_turns=2, mistakes=["grammar"])  # too short
    await seed_session(pid, sid, at=NOW, level="A1", mistakes=["grammar"])  # other level
    level = (await stats(client))["level"]
    assert level["direction"] == "up"
    assert level["suggested_level"] == "B1"
    assert level["average_error_rate"] == 0.0
    assert level["sessions_counted"] == 3


async def test_high_error_rate_suggests_moving_down_and_confirming_resets(
    client: AsyncClient,
) -> None:
    await onboard(client, level="B1")
    pid, sid = await profile_id(), await add_scenario()
    for days_ago in (3, 2, 1):
        await seed_session(
            pid,
            sid,
            at=NOW - timedelta(days=days_ago),
            learner_turns=1,
            mistakes=["grammar"],
            level="B1",
        )
    # Sessions with 1 learner message don't qualify.
    assert (await stats(client))["level"]["direction"] is None
    for days_ago in (3, 2, 1):
        await seed_session(
            pid,
            sid,
            at=NOW - timedelta(hours=days_ago),
            learner_turns=3,
            level="B1",
            mistakes=["grammar"],
        )
    async with get_session_factory()() as db:  # make every message in them a mistake
        rows = await db.execute(select(PracticeSession).where(PracticeSession.error_rate > 0))
        for s in rows.scalars():
            s.error_rate = Decimal("0.6667")
        await db.commit()
    level = (await stats(client))["level"]
    assert (level["direction"], level["suggested_level"]) == ("down", "A2")

    # The learner confirms: the old sessions were at B1, so nothing is suggested at A2.
    await client.put(
        "/profile", json={"native_language": "en", "target_language": "es", "cefr_level": "A2"}
    )
    level = (await stats(client))["level"]
    assert level["current_level"] == "A2" and level["direction"] is None


async def test_stats_are_per_language_but_streak_is_per_account(client: AsyncClient) -> None:
    await onboard(client, target="es")
    await seed_session(await profile_id(), await add_scenario(), at=NOW, mistakes=["grammar"])
    await client.put(
        "/profile", json={"native_language": "en", "target_language": "fr", "cefr_level": "A1"}
    )
    data = await stats(client)
    assert data["totals"]["sessions_completed"] == 0
    assert data["error_types"] == []
    assert data["streak"]["days"] == 1


async def test_stats_need_login_and_onboarding(client: AsyncClient) -> None:
    assert (await client.get("/stats")).status_code == 401
    from tests.conftest import register

    await register(client)
    assert (await client.get("/stats")).status_code == 409
