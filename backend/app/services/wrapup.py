"""Ending a session: one LLM call for the summary and vocab, then save both together."""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversation.prompt_builder import (
    WRAPUP_MAX_CORRECTIONS,
    CorrectionText,
    TurnText,
    build_wrapup_messages,
)
from app.llm.base import LLMClient
from app.models import Correction, PracticeSession, VocabItem
from app.schemas.vocab import SummaryOut, VocabOut, WrapUpResult
from app.schemas.wrapup import (
    MAX_VOCAB,
    CorrectionForVocab,
    WrapUpOut,
    cards_for_missed_corrections,
    select_vocab,
)
from app.services.analysis import wait_for_session
from app.services.practice_sessions import get_owned_session, session_scene
from app.services.vocab import NewVocab, add_items, dedupe, existing_terms, utc_now

logger = logging.getLogger(__name__)

# How long ending a session waits for corrections of the last messages to finish.
ANALYSIS_GRACE_SECONDS = 20.0


def error_rate(session: PracticeSession) -> Decimal | None:
    """Share of learner messages that had at least one correction, from 0 to 1."""
    learner = [t for t in session.turns if t.role == "learner"]
    if not learner:
        return None
    with_mistakes = sum(1 for t in learner if t.corrections)
    return (Decimal(with_mistakes) / Decimal(len(learner))).quantize(Decimal("0.0001"))


def parse_summary(raw: str | None) -> SummaryOut | None:
    """``sessions.summary`` holds the summary as JSON text."""
    if not raw:
        return None
    try:
        return SummaryOut.model_validate_json(raw)
    except ValueError:
        return SummaryOut(went_well=raw, recurring_mistakes=[], practice=[])


async def session_vocab(db: AsyncSession, session_id: int) -> list[VocabItem]:
    result = await db.execute(
        select(VocabItem).where(VocabItem.session_id == session_id).order_by(VocabItem.id)
    )
    return list(result.scalars())


async def existing_result(db: AsyncSession, session: PracticeSession) -> WrapUpResult:
    return WrapUpResult(
        session_id=session.id,
        summary=parse_summary(session.summary),
        error_rate=float(session.error_rate) if session.error_rate is not None else None,
        new_vocab=[VocabOut.model_validate(v) for v in await session_vocab(db, session.id)],
        skipped_duplicates=0,
    )


async def end_session(
    db: AsyncSession,
    session: PracticeSession,
    user_id: int,
    native_language: str,
    llm: LLMClient,
) -> WrapUpResult:
    """Run the wrap-up and end the session. Ending twice returns the first result.

    If the LLM fails, nothing is saved and the session stays open, so the learner can try
    again or keep talking.
    """
    if session.ended_at is not None:
        return await existing_result(db, session)

    await wait_for_session(session.id, ANALYSIS_GRACE_SECONDS)
    reloaded = await get_owned_session(db, session.id, user_id)
    assert reloaded is not None
    session = reloaded
    learner_turns = [t for t in session.turns if t.role == "learner"]
    # Read everything needed from the loaded turns now: locking the row below reloads it.
    rate = error_rate(session)
    profile_id = session.learner_profile_id
    language = session.learner_profile.target_language

    candidates: list[NewVocab] = []
    summary_json: str | None = None
    if learner_turns:
        corrections: list[Correction] = [c for t in learner_turns for c in t.corrections][
            -WRAPUP_MAX_CORRECTIONS:
        ]
        messages = build_wrapup_messages(
            session_scene(session, native_language),
            [TurnText(t.role, t.text) for t in session.turns],
            [CorrectionText(c.original, c.corrected, c.error_type) for c in corrections],
            MAX_VOCAB,
        )
        out = await llm.complete_json(messages, WrapUpOut, usage_tag=f"session:{session.id}:wrapup")
        summary_json = out.summary().model_dump_json()
        learner_texts = [t.text for t in learner_turns]
        known = frozenset(await existing_terms(db, profile_id, language))
        chosen = select_vocab(out.vocab, len(corrections), learner_texts, known, language)
        missed = cards_for_missed_corrections(
            chosen, [CorrectionForVocab(c.corrected, c.explanation) for c in corrections]
        )
        for v, index in [*chosen, *missed]:
            candidates.append(
                NewVocab(
                    term=v.term,
                    translation=v.translation,
                    example_sentence=v.example_sentence,
                    source_correction_id=corrections[index].id if index is not None else None,
                )
            )

    # Lock the row so two "end" requests can't both save a wrap-up.
    locked = (
        await db.execute(
            select(PracticeSession)
            .where(PracticeSession.id == session.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    if locked.ended_at is not None:
        await db.rollback()
        return await existing_result(db, locked)

    fresh, skipped = dedupe(candidates, await existing_terms(db, profile_id, language), language)
    now = utc_now()
    inserted_ids = await add_items(db, profile_id, session.id, fresh, now)
    skipped += len(fresh) - len(inserted_ids)
    locked.ended_at = now
    locked.summary = summary_json
    locked.error_rate = rate
    await db.commit()
    logger.info(
        "Ended session %d: %d vocab added, %d duplicates skipped",
        session.id,
        len(inserted_ids),
        skipped,
    )
    await db.refresh(locked)
    result = await existing_result(db, locked)
    return result.model_copy(update={"skipped_duplicates": skipped})
