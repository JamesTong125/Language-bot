"""Application settings, read from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Empty values (e.g. "LLM_FALLBACK_MODEL=") fall back to the defaults below.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = Field(
        default="postgresql+asyncpg://immersion:immersion@localhost:5432/immersion"
    )
    jwt_secret: str = Field(min_length=32)
    jwt_expiry_days: int = 7
    cors_origin: str = "http://localhost:3000"
    cookie_secure: bool = False
    log_level: str = "INFO"

    # --- LLM: conversation partner ---
    llm_chat_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_chat_api_key: str = ""
    llm_chat_model: str = "gemini-3.8-flash"
    llm_chat_max_tokens: int = 1024
    llm_chat_reasoning_effort: str = ""
    llm_chat_json_mode: bool = False

    # --- LLM: error analysis, wrap-up, hints ---
    llm_analysis_base_url: str = "https://api.groq.com/openai/v1"
    llm_analysis_api_key: str = ""
    llm_analysis_model: str = "openai/gpt-oss-20b"
    llm_analysis_max_tokens: int = 1024
    llm_analysis_reasoning_effort: str = ""
    llm_analysis_json_mode: bool = False

    # --- LLM: optional fallback when the main provider fails ---
    llm_fallback_base_url: str = ""
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = ""
    llm_fallback_max_tokens: int = 1024
    llm_fallback_reasoning_effort: str = ""
    llm_fallback_json_mode: bool = False

    # --- LLM: shared behaviour ---
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_daily_request_budget: int | None = None
    llm_history_turns: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
