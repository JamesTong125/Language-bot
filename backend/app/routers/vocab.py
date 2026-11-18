from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentProfile, CurrentUser, DbSession
from app.models import User, VocabItem
from app.schemas.vocab import (
    ReviewOut,
    ReviewQueue,
    ReviewRequest,
    VocabFilter,
    VocabOut,
    VocabPage,
)
from app.services.vocab import (
    delete_item,
    due_count,
    get_owned_item,
    list_deck,
    record_review,
    review_queue,
    utc_now,
)

router = APIRouter(prefix="/vocab", tags=["vocab"])


async def _load(db: DbSession, item_id: int, user: User) -> VocabItem:
    item = await get_owned_item(db, item_id, user.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return item


@router.get("")
async def get_deck(
    profile: CurrentProfile,
    db: DbSession,
    filter: VocabFilter = "all",
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> VocabPage:
    """The current language's deck, newest first."""
    now = utc_now()
    items, total = await list_deck(
        db, profile.id, kind=filter, query=q, page=page, page_size=page_size, now=now
    )
    return VocabPage(
        items=[VocabOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        due_count=await due_count(db, profile.id, now),
    )


@router.get("/review")
async def get_review_queue(
    profile: CurrentProfile,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> ReviewQueue:
    """Cards due now (due_at <= now), oldest due first."""
    now = utc_now()
    items = await review_queue(db, profile.id, limit, now)
    return ReviewQueue(
        items=[VocabOut.model_validate(i) for i in items],
        due_count=await due_count(db, profile.id, now),
    )


@router.post("/{item_id}/review")
async def post_review(
    item_id: int, body: ReviewRequest, user: CurrentUser, db: DbSession
) -> ReviewOut:
    item = await _load(db, item_id, user)
    now = utc_now()
    item, review = await record_review(db, item, body.rating, now)
    return ReviewOut(item=VocabOut.model_validate(item), reviewed_at=review.reviewed_at)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vocab(item_id: int, user: CurrentUser, db: DbSession) -> None:
    await delete_item(db, await _load(db, item_id, user))
