from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.languages import CefrLevel
from app.schemas.analysis import ErrorType


class Streak(BaseModel):
    days: int
    practised_today: bool


class WeekCount(BaseModel):
    week_start: date  # Monday, in the learner's time zone
    sessions: int


class SessionPoint(BaseModel):
    session_id: int
    ended_at: datetime
    scenario_title: str
    cefr_level: CefrLevel
    error_rate: float


class ErrorTypeCount(BaseModel):
    error_type: ErrorType
    count: int


class LevelProgress(BaseModel):
    current_level: CefrLevel
    direction: Literal["up", "down"] | None
    suggested_level: CefrLevel | None
    average_error_rate: float | None
    sessions_counted: int
    sessions_needed: int
    session_ids: list[int]
    up_threshold: float
    down_threshold: float


class Totals(BaseModel):
    sessions_completed: int
    learner_messages: int
    vocab_items: int
    vocab_due: int
    reviews: int


class StatsOut(BaseModel):
    time_zone: str
    streak: Streak
    totals: Totals
    sessions_per_week: list[WeekCount]
    error_rate_trend: list[SessionPoint]
    error_types: list[ErrorTypeCount]
    level: LevelProgress
