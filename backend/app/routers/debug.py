from datetime import timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import AppSettings, CurrentUser, DbSession
from app.llm.usage import utc_today
from app.models import LlmUsage

router = APIRouter(prefix="/debug", tags=["debug"])


class UsageRow(BaseModel):
    day: str
    provider: str
    model: str
    requests: int
    prompt_tokens: int
    completion_tokens: int


class UsageReport(BaseModel):
    daily_request_budget: int | None
    requests_today: int
    budget_used_fraction: float | None
    rows: list[UsageRow]


@router.get("/llm-usage")
async def llm_usage(
    _user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    days: int = Query(default=7, ge=1, le=90),
) -> UsageReport:
    """Requests and tokens per provider per UTC day. Aggregate only, no user data."""
    today = utc_today()
    result = await db.execute(
        select(LlmUsage)
        .where(LlmUsage.day > today - timedelta(days=days))
        .order_by(LlmUsage.day.desc(), LlmUsage.provider, LlmUsage.model)
    )
    rows = list(result.scalars())
    requests_today = sum(r.requests for r in rows if r.day == today)
    budget = settings.llm_daily_request_budget
    return UsageReport(
        daily_request_budget=budget,
        requests_today=requests_today,
        budget_used_fraction=round(requests_today / budget, 3) if budget else None,
        rows=[
            UsageRow(
                day=r.day.isoformat(),
                provider=r.provider,
                model=r.model,
                requests=r.requests,
                prompt_tokens=r.prompt_tokens,
                completion_tokens=r.completion_tokens,
            )
            for r in rows
        ],
    )
