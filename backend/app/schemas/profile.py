from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.languages import CefrLevel, is_supported


class ProfileUpdate(BaseModel):
    native_language: str
    target_language: str
    cefr_level: CefrLevel
    goals: str | None = Field(default=None, max_length=1000)

    @field_validator("native_language", "target_language")
    @classmethod
    def check_language(cls, value: str) -> str:
        if not is_supported(value):
            raise ValueError("Unsupported language")
        return value

    @field_validator("goals")
    @classmethod
    def blank_goals_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def languages_differ(self) -> "ProfileUpdate":
        if self.native_language == self.target_language:
            raise ValueError("Target language must differ from native language")
        return self


class LearnerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_language: str
    cefr_level: CefrLevel
    goals: str | None
    created_at: datetime
    updated_at: datetime


class ProfileOut(BaseModel):
    email: str
    native_language: str | None
    current: LearnerProfileOut | None
    profiles: list[LearnerProfileOut]
