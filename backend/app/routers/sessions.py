import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.deps import AnalysisLLM, AppSettings, ChatLLM, CurrentProfile, CurrentUser, DbSession
from app.llm.base import AllProvidersFailedError, LLMClient, LLMError, LLMNotConfiguredError
from app.models import PracticeSession, User
from app.schemas.conversation import (
    CorrectionOut,
    HintOut,
    ScenarioOut,
    SessionOut,
    StartSessionRequest,
    TurnOut,
    TurnRequest,
)
from app.schemas.vocab import WrapUpResult
from app.services.analysis import start_analysis
from app.services.practice_sessions import (
    ReplyPlan,
    add_learner_turn,
    analysis_input,
    get_owned_session,
    plan_reply,
    save_partner_turn,
    start_session,
    suggest_hint,
)
from app.services.scenarios import get_visible_scenario
from app.services.wrapup import end_session, existing_result
from app.sse import SSE_HEADERS, sse_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def session_out(session: PracticeSession, native_language: str) -> SessionOut:
    return SessionOut(
        id=session.id,
        scenario=ScenarioOut.model_validate(session.scenario),
        target_language=session.learner_profile.target_language,
        native_language=native_language,
        cefr_level=session.learner_profile.cefr_level,
        started_at=session.started_at,
        ended_at=session.ended_at,
        turns=[TurnOut.model_validate(t) for t in session.turns],
    )


def llm_error_message(exc: LLMError) -> str:
    if isinstance(exc, LLMNotConfiguredError):
        return "The AI partner isn't configured on the server yet."
    if isinstance(exc, AllProvidersFailedError):
        return exc.user_message
    return "The AI partner couldn't reply. Please try again."


async def _load(db: DbSession, session_id: int, user: User) -> PracticeSession:
    session = await get_owned_session(db, session_id, user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: StartSessionRequest,
    user: CurrentUser,
    profile: CurrentProfile,
    db: DbSession,
    llm: ChatLLM,
    settings: AppSettings,
) -> SessionOut:
    scenario = await get_visible_scenario(db, body.scenario_id, user.id, profile.target_language)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    try:
        session = await start_session(db, user, profile, scenario, llm, settings.llm_history_turns)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=llm_error_message(exc)
        ) from exc
    assert user.native_language
    return session_out(session, user.native_language)


@router.get("/{session_id}")
async def get_session(session_id: int, user: CurrentUser, db: DbSession) -> SessionOut:
    assert user.native_language
    return session_out(await _load(db, session_id, user), user.native_language)


# How long the stream stays open after the reply, waiting for corrections. If analysis takes
# longer, corrections are still saved and show up the next time the transcript is loaded.
ANALYSIS_WAIT_SECONDS = 45.0

AnalysisTask = asyncio.Task[list[CorrectionOut] | None]


async def _reply_events(
    plan: ReplyPlan,
    llm: LLMClient,
    learner_turn: TurnOut | None,
    analysis: AnalysisTask | None,
) -> AsyncIterator[str]:
    if learner_turn is not None:
        yield sse_event("learner_turn", learner_turn.model_dump(mode="json"))
    parts: list[str] = []
    try:
        async for chunk in llm.stream_chat(plan.messages, usage_tag=plan.usage_tag):
            parts.append(chunk)
            yield sse_event("token", {"text": chunk})
        text = "".join(parts).strip()
        if not text:
            raise LLMError("Empty reply")
        partner_turn = await save_partner_turn(plan.session_id, text)
        yield sse_event("done", partner_turn.model_dump(mode="json"))
    except LLMError as exc:
        logger.warning(
            "Partner reply failed for session %d: %s", plan.session_id, type(exc).__name__
        )
        yield sse_event("error", {"message": llm_error_message(exc), "retryable": True})

    if analysis is None or learner_turn is None:
        return
    try:
        # shield: if the wait times out or the client leaves, the analysis keeps running.
        corrections = await asyncio.wait_for(asyncio.shield(analysis), ANALYSIS_WAIT_SECONDS)
    except TimeoutError:
        logger.info("Analysis for turn %d still running; closing stream", learner_turn.id)
        return
    yield sse_event(
        "corrections",
        {
            "turn_id": learner_turn.id,
            "status": "failed" if corrections is None else "ok",
            "corrections": [c.model_dump(mode="json") for c in corrections or []],
        },
    )


@router.post("/{session_id}/turns")
async def post_turn(
    session_id: int,
    body: TurnRequest,
    user: CurrentUser,
    db: DbSession,
    llm: ChatLLM,
    analysis_llm: AnalysisLLM,
    settings: AppSettings,
) -> StreamingResponse:
    """Save the learner message, then stream the partner reply as SSE.

    Events: ``learner_turn`` (the saved message), ``token`` (reply text chunks), then
    ``done`` (the saved partner turn) or ``error`` (nothing saved; send ``{"retry": true}``
    to try again). For a new message, ``corrections`` follows once the background error
    analysis finishes. The learner message is kept either way.
    """
    session = await _load(db, session_id, user)
    if session.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This session has ended")
    assert user.native_language  # Sessions only exist for onboarded users.

    learner_turn: TurnOut | None = None
    analysis: AnalysisTask | None = None
    if body.text is not None:
        turn = await add_learner_turn(db, session, body.text)
        learner_turn = TurnOut.new(turn)
        session = await _load(db, session_id, user)
        # Start right away, so analysis runs alongside the partner reply.
        analysis = start_analysis(
            session.id,
            turn.id,
            analysis_input(session, user.native_language),
            analysis_llm,
            usage_tag=f"session:{session.id}:analysis",
        )
    elif not session.turns or session.turns[-1].role != "learner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="There is no message waiting for a reply"
        )

    plan = plan_reply(session, user.native_language, settings.llm_history_turns)
    return StreamingResponse(
        _reply_events(plan, llm, learner_turn, analysis),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/{session_id}/end")
async def post_end(
    session_id: int,
    user: CurrentUser,
    db: DbSession,
    llm: AnalysisLLM,
) -> WrapUpResult:
    """Run the wrap-up: summary, error rate, and new vocab cards (duplicates skipped).

    Ending an ended session returns its saved result. If the LLM fails, the session stays
    open and nothing is saved.
    """
    session = await _load(db, session_id, user)
    assert user.native_language
    try:
        return await end_session(db, session, user.id, user.native_language, llm)
    except LLMError as exc:
        logger.warning("Wrap-up failed for session %d: %s", session_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Couldn't write your session summary right now. Please try again.",
        ) from exc


@router.get("/{session_id}/summary")
async def get_summary(session_id: int, user: CurrentUser, db: DbSession) -> WrapUpResult:
    session = await _load(db, session_id, user)
    if session.ended_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This session is still open"
        )
    return await existing_result(db, session)


@router.post("/{session_id}/hint")
async def post_hint(
    session_id: int,
    user: CurrentUser,
    db: DbSession,
    llm: AnalysisLLM,
    settings: AppSettings,
) -> HintOut:
    session = await _load(db, session_id, user)
    assert user.native_language
    try:
        return await suggest_hint(session, user.native_language, llm, settings.llm_history_turns)
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Couldn't get a hint right now. Please try again.",
        ) from exc
