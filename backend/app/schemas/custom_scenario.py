"""Custom scenario requests and the validated LLM draft."""

from pydantic import BaseModel, Field, field_validator, model_validator

MIN_DESCRIPTION = 8
MAX_DESCRIPTION = 300


class CreateScenarioRequest(BaseModel):
    description: str = Field(max_length=MAX_DESCRIPTION)

    @field_validator("description")
    @classmethod
    def check_length(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < MIN_DESCRIPTION:
            raise ValueError(f"Describe the situation in at least {MIN_DESCRIPTION} characters")
        return value


class ScenarioDraft(BaseModel):
    """What the model returns. A refusal needs no other fields."""

    refused: bool = False
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    partner_persona: str | None = Field(default=None, max_length=400)
    goal: str | None = Field(default=None, max_length=300)

    @field_validator("title", "description", "partner_persona", "goal")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def complete_unless_refused(self) -> "ScenarioDraft":
        if self.refused:
            return self
        missing = [
            name
            for name in ("title", "description", "partner_persona", "goal")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}")
        if len(self.title or "") < 3:
            raise ValueError("title is too short")
        return self
