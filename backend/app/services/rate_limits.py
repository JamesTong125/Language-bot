"""Per-user rate limits, counted from rows already in the database.

No extra table or cache is needed, and limits hold across restarts and workers. The check
and the insert aren't atomic, so two requests at the same instant can both pass: these are
soft limits that protect the free-tier quota, not hard guarantees.
"""

import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from app.models import LearnerProfile, PracticeSession, Scenario, Turn

MINUTE = timedelta(minutes=1)
DAY = timedelta(days=1)


class RateLimitedError(Exception):
    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


async def _check(
    db: AsyncSession,
    model: type[Any],
    column: QueryableAttribute[datetime],
    conditions: list[ColumnElement[bool]],
    joins: list[tuple[type[Any], ColumnElement[bool]]],
    limit: int,
    window: timedelta,
    message: str,
) -> None:
    if limit <= 0:
        return
    stmt = select(func.count(), func.min(column), func.now()).select_from(model)
    for target, on in joins:
        stmt = stmt.join(target, on)
    stmt = stmt.where(*conditions, column > func.now() - window)
    count, oldest, now = (await db.execute(stmt)).one()
    if count < limit:
        return
    # The window frees up when the oldest counted row leaves it.
    wait = window.total_seconds()
    if isinstance(oldest, datetime) and isinstance(now, datetime):
        wait = (oldest + window - now).total_seconds()
    raise RateLimitedError(message, max(1, math.ceil(wait)))


async def check_turns(db: AsyncSession, user_id: int, per_minute: int) -> None:
    await _check(
        db,
        Turn,
        Turn.created_at,
        [Turn.role == "learner", LearnerProfile.user_id == user_id],
        [
            (PracticeSession, Turn.session_id == PracticeSession.id),
            (LearnerProfile, PracticeSession.learner_profile_id == LearnerProfile.id),
        ],
        per_minute,
        MINUTE,
        "You're sending messages very quickly. Wait a moment, then try again.",
    )


async def check_sessions(db: AsyncSession, user_id: int, per_day: int) -> None:
    await _check(
        db,
        PracticeSession,
        PracticeSession.started_at,
        [LearnerProfile.user_id == user_id],
        [(LearnerProfile, PracticeSession.learner_profile_id == LearnerProfile.id)],
        per_day,
        DAY,
        f"You've started {per_day} sessions in the last 24 hours, the daily limit. "
        "Try again later.",
    )


async def check_scenarios(db: AsyncSession, user_id: int, per_day: int) -> None:
    await _check(
        db,
        Scenario,
        Scenario.created_at,
        [Scenario.created_by == user_id],
        [],
        per_day,
        DAY,
        f"You've created {per_day} scenarios in the last 24 hours, the daily limit. "
        "Try again later.",
    )
