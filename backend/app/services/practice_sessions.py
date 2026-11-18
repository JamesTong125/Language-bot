"""Sessions and turns: persistence plus the partner-reply flow."""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.conversation.prompt_builder import (
    SceneContext,
    TurnText,
    build_hint_messages,
    build_partner_messages,
)
from app.db import get_session_factory
from app.llm.base import LLMClient, Message
from app.models import LearnerProfile, PracticeSession, Scenario, Turn, User
from app.schemas.conversation import HintOut

logger = logging.getLogger(__name__)


class NotOnboardedError(Exception):
    pass


def scene_for(scenario: Scenario, profile: LearnerProfile, native_language: str) -> SceneContext:
    return SceneContext(
        title=scenario.title,
        description=scenario.description,
        persona=scenario.partner_persona,
        goal=scenario.goal,
        target_language=profile.target_language,
        native_language=native_language,
        level=profile.cefr_level,
    )


def _turn_texts(turns: list[Turn]) -> list[TurnText]:
    return [TurnText(role=t.role, text=t.text) for t in turns]


async def collect(stream: AsyncIterator[str]) -> str:
    return "".join([chunk async for chunk in stream]).strip()


async def start_session(
    db: AsyncSession,
    user: User,
    profile: LearnerProfile,
    scenario: Scenario,
    llm: LLMClient,
    history_limit: int,
) -> PracticeSession:
    """Generate the opening line first, then save the session and turn together.

    If the LLM fails, nothing is saved and the error propagates.
    """
    if not user.native_language:
        raise NotOnboardedError
    scene = scene_for(scenario, profile, user.native_language)
    messages = build_partner_messages(scene, [], history_limit)
    opening = await collect(llm.stream_chat(messages, usage_tag="session:new"))

    session = PracticeSession(learner_profile_id=profile.id, scenario_id=scenario.id)
    db.add(session)
    await db.flush()
    db.add(Turn(session_id=session.id, role="partner", text=opening))
    await db.commit()
    logger.info("Started session %d (scenario %d)", session.id, scenario.id)
    loaded = await get_owned_session(db, session.id, user.id)
    assert loaded is not None
    return loaded


async def get_owned_session(
    db: AsyncSession, session_id: int, user_id: int
) -> PracticeSession | None:
    result = await db.execute(
        select(PracticeSession)
        .join(LearnerProfile, PracticeSession.learner_profile_id == LearnerProfile.id)
        .where(PracticeSession.id == session_id, LearnerProfile.user_id == user_id)
        .options(
            selectinload(PracticeSession.scenario),
            selectinload(PracticeSession.learner_profile),
            selectinload(PracticeSession.turns),
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def add_learner_turn(db: AsyncSession, session: PracticeSession, text: str) -> Turn:
    turn = Turn(session_id=session.id, role="learner", text=text)
    db.add(turn)
    await db.commit()
    await db.refresh(turn)
    return turn


@dataclass(frozen=True)
class ReplyPlan:
    """Everything the streaming reply needs, captured before the request's DB session ends."""

    session_id: int
    messages: list[Message]
    usage_tag: str


def plan_reply(session: PracticeSession, native_language: str, history_limit: int) -> ReplyPlan:
    scene = scene_for(session.scenario, session.learner_profile, native_language)
    return ReplyPlan(
        session_id=session.id,
        messages=build_partner_messages(scene, _turn_texts(session.turns), history_limit),
        usage_tag=f"session:{session.id}",
    )


async def save_partner_turn(session_id: int, text: str) -> Turn:
    """Uses its own DB session: it runs inside a streaming response."""
    async with get_session_factory()() as db:
        turn = Turn(session_id=session_id, role="partner", text=text)
        db.add(turn)
        await db.commit()
        await db.refresh(turn)
        return turn


async def suggest_hint(
    session: PracticeSession, native_language: str, llm: LLMClient, history_limit: int
) -> HintOut:
    scene = scene_for(session.scenario, session.learner_profile, native_language)
    messages = build_hint_messages(scene, _turn_texts(session.turns), history_limit)
    return await llm.complete_json(messages, HintOut, usage_tag=f"session:{session.id}:hint")
