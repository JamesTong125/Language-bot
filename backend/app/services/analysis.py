"""Background error analysis of learner turns.

Runs as an asyncio task next to the streamed partner reply, so the reply is never delayed.
FastAPI's BackgroundTasks would only start after the streaming response ends.
"""

import asyncio
import logging

from app.conversation.prompt_builder import AnalysisInput, build_analysis_messages
from app.db import get_session_factory
from app.llm.base import LLMClient, LLMError
from app.models import Correction
from app.schemas.analysis import AnalysisOut, usable_corrections
from app.schemas.conversation import CorrectionOut

logger = logging.getLogger(__name__)

AnalysisTask = asyncio.Task[list[CorrectionOut] | None]

# Strong references so running tasks aren't garbage collected mid-flight.
_running: set[AnalysisTask] = set()
_by_session: dict[int, set[AnalysisTask]] = {}


async def analyse_turn(
    turn_id: int, item: AnalysisInput, llm: LLMClient, usage_tag: str
) -> list[CorrectionOut] | None:
    """Analyse one learner turn and save its corrections.

    Returns the saved corrections (possibly empty), or None if the analysis failed. On
    failure nothing is stored. No exception escapes: analysis must never break the chat.
    """
    try:
        analysis = await llm.complete_json(
            build_analysis_messages(item), AnalysisOut, usage_tag=usage_tag
        )
        found = usable_corrections(analysis, item.learner_text)
        async with get_session_factory()() as db:
            rows = [
                Correction(
                    turn_id=turn_id,
                    original=c.original,
                    corrected=c.corrected,
                    error_type=c.error_type,
                    explanation=c.explanation,
                    severity=c.severity,
                )
                for c in found
            ]
            db.add_all(rows)
            await db.commit()
            saved = [CorrectionOut.model_validate(r) for r in rows]
        logger.info("Turn %d analysed: %d corrections", turn_id, len(saved))
        return saved
    except LLMError as exc:
        logger.warning("Analysis failed for turn %d: %s", turn_id, type(exc).__name__)
    except Exception:
        logger.exception("Unexpected error analysing turn %d", turn_id)
    return None


def start_analysis(
    session_id: int, turn_id: int, item: AnalysisInput, llm: LLMClient, usage_tag: str
) -> AnalysisTask:
    task = asyncio.create_task(analyse_turn(turn_id, item, llm, usage_tag))
    _running.add(task)
    _by_session.setdefault(session_id, set()).add(task)

    def forget(done: AnalysisTask) -> None:
        _running.discard(done)
        tasks = _by_session.get(session_id)
        if tasks is not None:
            tasks.discard(done)
            if not tasks:
                _by_session.pop(session_id, None)

    task.add_done_callback(forget)
    return task


async def wait_for_session(session_id: int, grace_seconds: float) -> None:
    """Wait (up to ``grace_seconds``) for this session's analyses still in progress."""
    tasks = list(_by_session.get(session_id, ()))
    if tasks:
        await asyncio.wait(tasks, timeout=grace_seconds)
