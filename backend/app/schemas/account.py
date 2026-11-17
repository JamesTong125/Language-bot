from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.profile import LearnerProfileOut


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class ExportedUser(BaseModel):
    id: int
    email: str
    native_language: str | None
    created_at: datetime


class AccountExport(BaseModel):
    """Everything stored about a user. Later phases add sessions, vocab, and reviews."""

    format_version: int = 1
    exported_at: datetime
    user: ExportedUser
    learner_profiles: list[LearnerProfileOut]
