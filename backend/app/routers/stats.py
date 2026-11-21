from fastapi import APIRouter, Query

from app.deps import CurrentProfile, CurrentUser, DbSession
from app.schemas.stats import StatsOut
from app.services.stats import build_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_stats(
    user: CurrentUser,
    profile: CurrentProfile,
    db: DbSession,
    tz: str | None = Query(default=None, max_length=64, description="IANA time zone"),
) -> StatsOut:
    """Streak, sessions per week, error rate trend, common error types, and level progress."""
    return await build_stats(db, user.id, profile, tz)
