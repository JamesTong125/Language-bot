"""Scenario lookup. Learners see built-in scenarios plus their own custom ones."""

from sqlalchemy import ColumnElement, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.languages import CEFR_LEVELS
from app.models import Scenario

_LEVEL_RANK = case(
    {level: rank for rank, level in enumerate(CEFR_LEVELS)}, value=Scenario.cefr_level
)


def _visible_to(user_id: int, target_language: str) -> list[ColumnElement[bool]]:
    return [
        or_(Scenario.created_by.is_(None), Scenario.created_by == user_id),
        or_(Scenario.target_language.is_(None), Scenario.target_language == target_language),
    ]


async def list_scenarios(db: AsyncSession, user_id: int, target_language: str) -> list[Scenario]:
    """Custom scenarios first, then built-ins from easiest to hardest."""
    result = await db.execute(
        select(Scenario)
        .where(*_visible_to(user_id, target_language))
        .order_by(Scenario.is_custom.desc(), _LEVEL_RANK, Scenario.id)
    )
    return list(result.scalars())


async def get_visible_scenario(
    db: AsyncSession, scenario_id: int, user_id: int, target_language: str
) -> Scenario | None:
    result = await db.execute(
        select(Scenario).where(Scenario.id == scenario_id, *_visible_to(user_id, target_language))
    )
    return result.scalar_one_or_none()
