"""Builds the data export for a user. Extend this whenever a table gains user data."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import LearnerProfile, PracticeSession, Review, Scenario, Turn, User, VocabItem
from app.schemas.account import (
    AccountExport,
    ExportedReview,
    ExportedSession,
    ExportedUser,
    ExportedVocab,
)
from app.schemas.conversation import ScenarioOut, TurnOut
from app.schemas.profile import LearnerProfileOut
from app.schemas.vocab import VocabOut
from app.services.profiles import list_profiles
from app.services.wrapup import parse_summary


async def build_export(db: AsyncSession, user: User) -> AccountExport:
    profiles = await list_profiles(db, user.id)
    custom = await db.execute(
        select(Scenario).where(Scenario.created_by == user.id).order_by(Scenario.id)
    )
    sessions = await db.execute(
        select(PracticeSession)
        .join(LearnerProfile, PracticeSession.learner_profile_id == LearnerProfile.id)
        .where(LearnerProfile.user_id == user.id)
        .options(
            selectinload(PracticeSession.scenario),
            selectinload(PracticeSession.turns).selectinload(Turn.corrections),
        )
        .order_by(PracticeSession.id)
    )
    vocab = list(
        (
            await db.execute(
                select(VocabItem)
                .join(LearnerProfile, VocabItem.learner_profile_id == LearnerProfile.id)
                .where(LearnerProfile.user_id == user.id)
                .order_by(VocabItem.id)
            )
        ).scalars()
    )
    reviews_by_item: dict[int, list[Review]] = {}
    if vocab:
        reviews = await db.execute(
            select(Review)
            .where(Review.vocab_item_id.in_([v.id for v in vocab]))
            .order_by(Review.reviewed_at, Review.id)
        )
        for r in reviews.scalars():
            reviews_by_item.setdefault(r.vocab_item_id, []).append(r)
    return AccountExport(
        exported_at=datetime.now(UTC),
        user=ExportedUser(
            id=user.id,
            email=user.email,
            native_language=user.native_language,
            created_at=user.created_at,
        ),
        learner_profiles=[LearnerProfileOut.model_validate(p) for p in profiles],
        custom_scenarios=[ScenarioOut.model_validate(s) for s in custom.scalars()],
        sessions=[
            ExportedSession(
                id=s.id,
                learner_profile_id=s.learner_profile_id,
                scenario_id=s.scenario_id,
                scenario_title=s.scenario.title,
                cefr_level=s.cefr_level,
                is_private=s.is_private,
                started_at=s.started_at,
                ended_at=s.ended_at,
                summary=parse_summary(s.summary),
                error_rate=float(s.error_rate) if s.error_rate is not None else None,
                turns=[TurnOut.model_validate(t) for t in s.turns],
            )
            for s in sessions.scalars()
        ],
        vocab_items=[
            ExportedVocab(
                **VocabOut.model_validate(v).model_dump(),
                learner_profile_id=v.learner_profile_id,
                reviews=[
                    ExportedReview(rating=r.rating, reviewed_at=r.reviewed_at)
                    for r in reviews_by_item.get(v.id, [])
                ],
            )
            for v in vocab
        ],
    )
