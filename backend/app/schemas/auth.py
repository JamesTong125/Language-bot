from pydantic import BaseModel, EmailStr, Field, field_validator

from app.languages import is_supported


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class RegisterRequest(Credentials):
    native_language: str | None = None

    @field_validator("native_language")
    @classmethod
    def check_language(cls, value: str | None) -> str | None:
        if value is not None and not is_supported(value):
            raise ValueError("Unsupported language")
        return value


class LoginRequest(Credentials):
    # Login must not reject old passwords that predate a policy change.
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    native_language: str | None
