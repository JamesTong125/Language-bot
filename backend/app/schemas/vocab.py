from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VocabOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    term: str
    translation: str
    example_sentence: str | None
    source_correction_id: int | None
    session_id: int | None
    ease: float
    interval_days: int
    repetitions: int
    due_at: datetime
    created_at: datetime


class VocabPage(BaseModel):
    items: list[VocabOut]
    total: int
    page: int
    page_size: int
    due_count: int


VocabFilter = Literal["all", "due", "new", "learning", "mistakes"]


class ReviewQueue(BaseModel):
    items: list[VocabOut]
    due_count: int


class ReviewRequest(BaseModel):
    rating: int = Field(ge=0, le=5)


class ReviewOut(BaseModel):
    item: VocabOut
    reviewed_at: datetime


class SummaryOut(BaseModel):
    went_well: str
    recurring_mistakes: list[str]
    practice: list[str]


class WrapUpResult(BaseModel):
    session_id: int
    summary: SummaryOut | None
    error_rate: float | None
    new_vocab: list[VocabOut]
    skipped_duplicates: int
