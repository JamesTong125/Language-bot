from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.languages import CefrLevel
from app.schemas.analysis import ErrorType


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    partner_persona: str
    goal: str
    target_language: str | None
    cefr_level: CefrLevel
    is_custom: bool


class ScenarioList(BaseModel):
    scenarios: list[ScenarioOut]


class StartSessionRequest(BaseModel):
    scenario_id: int


class CorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original: str
    corrected: str
    error_type: ErrorType
    explanation: str
    severity: int


class TurnOut(BaseModel):
    """Build from a Turn loaded with its corrections (selectinload). For a turn created in
    this request, use ``TurnOut.new``: lazy-loading corrections isn't possible in async."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["learner", "partner"]
    text: str
    created_at: datetime
    corrections: list[CorrectionOut] = []

    @classmethod
    def new(cls, turn: Any) -> "TurnOut":
        return cls(id=turn.id, role=turn.role, text=turn.text, created_at=turn.created_at)


class SessionOut(BaseModel):
    id: int
    scenario: ScenarioOut
    target_language: str
    native_language: str
    cefr_level: CefrLevel
    started_at: datetime
    ended_at: datetime | None
    turns: list[TurnOut]


MAX_TURN_CHARS = 1000


class TurnRequest(BaseModel):
    """Send ``text`` for a new learner message, or ``retry: true`` to re-request the
    partner reply to the last learner message after a failure."""

    text: str | None = Field(default=None, max_length=MAX_TURN_CHARS)
    retry: bool = False

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def text_or_retry(self) -> "TurnRequest":
        if self.retry == (self.text is not None):
            raise ValueError("Send either a non-empty text or retry: true")
        return self


class HintOut(BaseModel):
    """Validated LLM output for the hint call, and the API response."""

    suggestions: list[str] = Field(min_length=1, max_length=3)

    @field_validator("suggestions")
    @classmethod
    def clean(cls, values: list[str]) -> list[str]:
        cleaned = [v.strip() for v in values if v.strip()]
        if not cleaned:
            raise ValueError("At least one non-empty suggestion is required")
        if any(len(v) > 200 for v in cleaned):
            raise ValueError("Each suggestion must be under 200 characters")
        return cleaned
