"""Application settings, read from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://immersion:immersion@localhost:5432/immersion"
    )
    jwt_secret: str = Field(min_length=32)
    jwt_expiry_days: int = 7
    cors_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
