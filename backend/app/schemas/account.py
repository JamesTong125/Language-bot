from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.conversation import ScenarioOut, TurnOut
from app.schemas.profile import LearnerProfileOut


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class ExportedUser(BaseModel):
    id: int
    email: str
    native_language: str | None
    created_at: datetime


class ExportedSession(BaseModel):
    id: int
    learner_profile_id: int
    scenario_id: int
    scenario_title: str
    started_at: datetime
    ended_at: datetime | None
    summary: str | None
    error_rate: float | None
    turns: list[TurnOut]


class AccountExport(BaseModel):
    """Everything stored about a user. Extend whenever a table gains user data."""

    format_version: int = 2
    exported_at: datetime
    user: ExportedUser
    learner_profiles: list[LearnerProfileOut]
    custom_scenarios: list[ScenarioOut]
    sessions: list[ExportedSession]
