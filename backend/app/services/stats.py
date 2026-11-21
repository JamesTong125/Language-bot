"""Progress statistics for the dashboard and level suggestions.

Local dates are computed in Postgres with the learner's time zone, so "today" and weeks
match the learner's own calendar. The streak covers the whole account; everything else is
for the current language (learner profile).
"""

from datetime import date, datetime

from sqlalchemy import Date, cast, func, select, text, union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    Correction,
    LearnerProfile,
    PracticeSession,
    Review,
    Scenario,
    Turn,
    VocabItem,
)
from app.progress.calendar import first_week_start, sessions_per_week, streak_days
from app.progress.level import (
    DOWN_THRESHOLD,
    MIN_LEARNER_TURNS,
    UP_THRESHOLD,
    WINDOW,
    SessionRate,
    suggest_level,
)
from app.schemas.stats import (
    ErrorTypeCount,
    LevelProgress,
    SessionPoint,
    StatsOut,
    Streak,
    Totals,
    WeekCount,
)

WEEKS = 8
TREND_SESSIONS = 10
DEFAULT_TIME_ZONE = "UTC"


async def resolve_time_zone(db: AsyncSession, tz: str | None) -> str:
    """Use the browser's IANA zone if Postgres knows it, else UTC."""
    if not tz or len(tz) > 64:
        return DEFAULT_TIME_ZONE
    query = text("SELECT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = :tz)")
    known = (await db.execute(query, {"tz": tz})).scalar_one()
    return tz if known else DEFAULT_TIME_ZONE


def _local_date(
    tz: str, column: ColumnElement[datetime] | QueryableAttribute[datetime]
) -> ColumnElement[date]:
    return cast(func.timezone(tz, column), Date)


async def _today(db: AsyncSession, tz: str) -> date:
    return (await db.execute(select(_local_date(tz, func.now())))).scalar_one()


async def _streak(db: AsyncSession, user_id: int, tz: str, today: date) -> Streak:
    turn_days = (
        select(_local_date(tz, Turn.created_at).label("day"))
        .join(PracticeSession, Turn.session_id == PracticeSession.id)
        .join(LearnerProfile, PracticeSession.learner_profile_id == LearnerProfile.id)
        .where(LearnerProfile.user_id == user_id, Turn.role == "learner")
    )
    review_days = (
        select(_local_date(tz, Review.reviewed_at).label("day"))
        .join(VocabItem, Review.vocab_item_id == VocabItem.id)
        .join(LearnerProfile, VocabItem.learner_profile_id == LearnerProfile.id)
        .where(LearnerProfile.user_id == user_id)
    )
    days = union(turn_days, review_days).subquery()
    active = set((await db.execute(select(days.c.day))).scalars())
    count, today_done = streak_days(active, today)
    return Streak(days=count, practised_today=today_done)


async def _sessions_per_week(
    db: AsyncSession, profile_id: int, tz: str, today: date
) -> list[WeekCount]:
    started = _local_date(tz, PracticeSession.started_at)
    result = await db.execute(
        select(started).where(
            PracticeSession.learner_profile_id == profile_id,
            started >= first_week_start(today, WEEKS),
        )
    )
    return [
        WeekCount(week_start=start, sessions=count)
        for start, count in sessions_per_week(result.scalars(), today, WEEKS)
    ]


async def _trend(db: AsyncSession, profile_id: int) -> list[SessionPoint]:
    result = await db.execute(
        select(PracticeSession, Scenario.title)
        .join(Scenario, PracticeSession.scenario_id == Scenario.id)
        .where(
            PracticeSession.learner_profile_id == profile_id,
            PracticeSession.ended_at.is_not(None),
            PracticeSession.error_rate.is_not(None),
        )
        .order_by(PracticeSession.ended_at.desc(), PracticeSession.id.desc())
        .limit(TREND_SESSIONS)
    )
    points = [
        SessionPoint(
            session_id=s.id,
            ended_at=s.ended_at,
            scenario_title=title,
            cefr_level=s.cefr_level,
            error_rate=float(s.error_rate or 0),
        )
        for s, title in result.all()
    ]
    return list(reversed(points))


async def _error_types(db: AsyncSession, profile_id: int) -> list[ErrorTypeCount]:
    count = func.count(Correction.id)
    result = await db.execute(
        select(Correction.error_type, count)
        .join(Turn, Correction.turn_id == Turn.id)
        .join(PracticeSession, Turn.session_id == PracticeSession.id)
        .where(PracticeSession.learner_profile_id == profile_id)
        .group_by(Correction.error_type)
        .order_by(count.desc(), Correction.error_type)
    )
    return [ErrorTypeCount(error_type=t, count=n) for t, n in result.all()]


async def _totals(db: AsyncSession, profile_id: int) -> Totals:
    in_profile = PracticeSession.learner_profile_id == profile_id
    sessions_completed = select(func.count()).where(
        in_profile, PracticeSession.ended_at.is_not(None)
    )
    learner_messages = (
        select(func.count())
        .select_from(Turn)
        .join(PracticeSession, Turn.session_id == PracticeSession.id)
        .where(in_profile, Turn.role == "learner")
    )
    deck = VocabItem.learner_profile_id == profile_id
    vocab_items = select(func.count()).select_from(VocabItem).where(deck)
    vocab_due = (
        select(func.count()).select_from(VocabItem).where(deck, VocabItem.due_at <= func.now())
    )
    reviews = (
        select(func.count())
        .select_from(Review)
        .join(VocabItem, Review.vocab_item_id == VocabItem.id)
        .where(deck)
    )
    row = (
        await db.execute(
            select(
                sessions_completed.select_from(PracticeSession).scalar_subquery(),
                learner_messages.scalar_subquery(),
                vocab_items.scalar_subquery(),
                vocab_due.scalar_subquery(),
                reviews.scalar_subquery(),
            )
        )
    ).one()
    return Totals(
        sessions_completed=row[0],
        learner_messages=row[1],
        vocab_items=row[2],
        vocab_due=row[3],
        reviews=row[4],
    )


async def level_progress(db: AsyncSession, profile: LearnerProfile) -> LevelProgress:
    learner_turns = (
        select(func.count())
        .select_from(Turn)
        .where(Turn.session_id == PracticeSession.id, Turn.role == "learner")
        .correlate(PracticeSession)
        .scalar_subquery()
    )
    result = await db.execute(
        select(PracticeSession.id, PracticeSession.error_rate)
        .where(
            PracticeSession.learner_profile_id == profile.id,
            PracticeSession.ended_at.is_not(None),
            PracticeSession.error_rate.is_not(None),
            PracticeSession.cefr_level == profile.cefr_level,
            learner_turns >= MIN_LEARNER_TURNS,
        )
        .order_by(PracticeSession.ended_at.desc(), PracticeSession.id.desc())
        .limit(WINDOW)
    )
    recent = [SessionRate(session_id=i, error_rate=float(r or 0)) for i, r in result.all()]
    s = suggest_level(profile.cefr_level, recent)
    return LevelProgress(
        current_level=s.current_level,
        direction=s.direction,
        suggested_level=s.suggested_level,
        average_error_rate=s.average_error_rate,
        sessions_counted=s.sessions_counted,
        sessions_needed=s.sessions_needed,
        session_ids=s.session_ids,
        up_threshold=UP_THRESHOLD,
        down_threshold=DOWN_THRESHOLD,
    )


async def build_stats(
    db: AsyncSession, user_id: int, profile: LearnerProfile, tz: str | None
) -> StatsOut:
    zone = await resolve_time_zone(db, tz)
    today = await _today(db, zone)
    return StatsOut(
        time_zone=zone,
        streak=await _streak(db, user_id, zone, today),
        totals=await _totals(db, profile.id),
        sessions_per_week=await _sessions_per_week(db, profile.id, zone, today),
        error_rate_trend=await _trend(db, profile.id),
        error_types=await _error_types(db, profile.id),
        level=await level_progress(db, profile),
    )
