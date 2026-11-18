"""The vocab deck: queries, the review queue, ratings, and deduplicated inserts."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearnerProfile, Review, VocabItem
from app.schemas.vocab import VocabFilter
from app.schemas.wrapup import normalise_term
from app.srs.scheduler import SrsState, new_card, schedule


def utc_now() -> datetime:
    return datetime.now(UTC)


def _owned(user_id: int) -> Select[VocabItem]:
    return (
        select(VocabItem)
        .join(LearnerProfile, VocabItem.learner_profile_id == LearnerProfile.id)
        .where(LearnerProfile.user_id == user_id)
    )


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _filter(kind: VocabFilter, now: datetime) -> ColumnElement[bool] | None:
    if kind == "due":
        return VocabItem.due_at <= now
    if kind == "new":
        return VocabItem.repetitions == 0
    if kind == "learning":
        return VocabItem.repetitions > 0
    if kind == "mistakes":
        return VocabItem.source_correction_id.is_not(None)
    return None


async def due_count(db: AsyncSession, profile_id: int, now: datetime) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(VocabItem)
        .where(VocabItem.learner_profile_id == profile_id, VocabItem.due_at <= now)
    )
    return int(result.scalar_one())


async def list_deck(
    db: AsyncSession,
    profile_id: int,
    *,
    kind: VocabFilter,
    query: str | None,
    page: int,
    page_size: int,
    now: datetime,
) -> tuple[list[VocabItem], int]:
    conditions: list[ColumnElement[bool]] = [VocabItem.learner_profile_id == profile_id]
    if (extra := _filter(kind, now)) is not None:
        conditions.append(extra)
    if query and query.strip():
        pattern = _like(query.strip())
        conditions.append(
            or_(
                VocabItem.term.ilike(pattern, escape="\\"),
                VocabItem.translation.ilike(pattern, escape="\\"),
            )
        )
    where = and_(*conditions)
    total = (
        await db.execute(select(func.count()).select_from(VocabItem).where(where))
    ).scalar_one()
    result = await db.execute(
        select(VocabItem)
        .where(where)
        .order_by(VocabItem.created_at.desc(), VocabItem.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars()), int(total)


async def review_queue(
    db: AsyncSession, profile_id: int, limit: int, now: datetime
) -> list[VocabItem]:
    """Cards due now, oldest due first."""
    result = await db.execute(
        select(VocabItem)
        .where(VocabItem.learner_profile_id == profile_id, VocabItem.due_at <= now)
        .order_by(VocabItem.due_at, VocabItem.id)
        .limit(limit)
    )
    return list(result.scalars())


async def get_owned_item(db: AsyncSession, item_id: int, user_id: int) -> VocabItem | None:
    result = await db.execute(_owned(user_id).where(VocabItem.id == item_id))
    return result.scalar_one_or_none()


async def record_review(
    db: AsyncSession, item: VocabItem, rating: int, now: datetime
) -> tuple[VocabItem, Review]:
    state = schedule(
        SrsState(item.ease, item.interval_days, item.repetitions, item.due_at), rating, now
    )
    item.ease = state.ease
    item.interval_days = state.interval_days
    item.repetitions = state.repetitions
    item.due_at = state.due_at
    review = Review(vocab_item_id=item.id, rating=rating, reviewed_at=now)
    db.add(review)
    await db.commit()
    await db.refresh(item)
    return item, review


async def delete_item(db: AsyncSession, item: VocabItem) -> None:
    await db.delete(item)
    await db.commit()


@dataclass(frozen=True)
class NewVocab:
    term: str
    translation: str
    example_sentence: str | None
    source_correction_id: int | None


async def existing_terms(
    db: AsyncSession, profile_id: int, language: str | None = None
) -> set[str]:
    result = await db.execute(
        select(VocabItem.term).where(VocabItem.learner_profile_id == profile_id)
    )
    return {normalise_term(t, language) for t in result.scalars()}


def dedupe(
    candidates: Sequence[NewVocab], known: set[str], language: str | None = None
) -> tuple[list[NewVocab], int]:
    """Drop candidates whose term is already in the deck or repeated in the batch.

    ``known`` must be normalised with the same ``language``.
    """
    seen = set(known)
    kept: list[NewVocab] = []
    for c in candidates:
        key = normalise_term(c.term, language)
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append(c)
    return kept, len(candidates) - len(kept)


async def add_items(
    db: AsyncSession,
    profile_id: int,
    session_id: int,
    items: Sequence[NewVocab],
    now: datetime,
) -> list[int]:
    """Insert new cards, due now. Skips any that race with an existing lower(term).

    Does not commit, so the caller can save the session wrap-up in the same transaction.
    """
    if not items:
        return []
    card = new_card(now)
    stmt = (
        insert(VocabItem)
        .values(
            [
                {
                    "learner_profile_id": profile_id,
                    "session_id": session_id,
                    "term": i.term,
                    "translation": i.translation,
                    "example_sentence": i.example_sentence,
                    "source_correction_id": i.source_correction_id,
                    "ease": card.ease,
                    "interval_days": card.interval_days,
                    "repetitions": card.repetitions,
                    "due_at": card.due_at,
                }
                for i in items
            ]
        )
        .on_conflict_do_nothing()
        .returning(VocabItem.id)
    )
    return list((await db.execute(stmt)).scalars())
