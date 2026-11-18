"""Records LLM requests and tokens per provider per day, and logs usage per session."""

import logging
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.llm.base import Usage
from app.models import LlmUsage

logger = logging.getLogger(__name__)


def utc_today() -> date:
    return datetime.now(UTC).date()


class UsageRecorder:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], daily_budget: int | None
    ) -> None:
        self._session_factory = session_factory
        self._daily_budget = daily_budget

    async def __call__(self, usage: Usage, tag: str | None) -> None:
        # Token counts only; transcript text is never logged.
        logger.info(
            "llm_usage tag=%s provider=%s model=%s prompt_tokens=%d completion_tokens=%d",
            tag or "-",
            usage.provider,
            usage.model,
            usage.prompt_tokens,
            usage.completion_tokens,
        )
        today = utc_today()
        insert_row = insert(LlmUsage).values(
            day=today,
            provider=usage.provider,
            model=usage.model,
            requests=1,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
        stmt = insert_row.on_conflict_do_update(
            index_elements=["day", "provider", "model"],
            set_={
                "requests": LlmUsage.requests + 1,
                "prompt_tokens": LlmUsage.prompt_tokens + insert_row.excluded.prompt_tokens,
                "completion_tokens": LlmUsage.completion_tokens
                + insert_row.excluded.completion_tokens,
            },
        ).returning(LlmUsage.requests)
        async with self._session_factory() as db:
            requests_today = (await db.execute(stmt)).scalar_one()
            await db.commit()
            if self._daily_budget:
                total = (
                    await db.execute(
                        select(func.sum(LlmUsage.requests)).where(LlmUsage.day == today)
                    )
                ).scalar_one()
                self._warn_if_near_budget(int(total or requests_today))

    def _warn_if_near_budget(self, total_today: int) -> None:
        assert self._daily_budget
        if total_today >= self._daily_budget:
            logger.warning(
                "LLM daily request budget exceeded: %d of %d", total_today, self._daily_budget
            )
        elif total_today >= 0.8 * self._daily_budget:
            logger.warning(
                "LLM daily request budget at %d%%: %d of %d",
                100 * total_today // self._daily_budget,
                total_today,
                self._daily_budget,
            )
