from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MIN_JWT_SECRET_LEN = 32


class Settings(BaseSettings):
    # hide_input_in_errors: a rejected secret must never be echoed in validation errors/logs.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True, populate_by_name=True
    )

    # AI_API_KEY is the name used in the hackathon brief; GROQ_API_KEY also works.
    groq_api_key: SecretStr = Field(validation_alias=AliasChoices("GROQ_API_KEY", "AI_API_KEY"))
    gemini_api_key: SecretStr | None = None
    openai_tracing_key: SecretStr | None = None
    jwt_secret: SecretStr

    database_url: str = "sqlite:///./hcm_ai.db"
    chat_model: str = "openai/gpt-oss-120b"
    fast_model: str = "openai/gpt-oss-20b"
    # Reasoning models spend output tokens on thinking; "low" keeps answers fast and inside
    # chat_max_tokens. Set to an empty value for models without reasoning support.
    reasoning_effort: str | None = "low"
    ai_timeout_seconds: float = 15
    ai_rate_limit_per_hour: int = 20
    gemini_model: str = "gemini-2.5-flash"
    agent_max_turns: int = 5
    chat_max_tokens: int = 512
    cors_origins: str = ""  # comma-separated; empty = no cross-origin access
    app_timezone: str = "Asia/Karachi"  # "today" for leave dates is computed in this zone
    enable_docs: bool = False
    demo_mode: bool = False  # exposes POST /auth/demo-login; never enable in production
    max_body_bytes: int = 32_768

    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    @field_validator("jwt_secret")
    @classmethod
    def _strong_jwt_secret(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < _MIN_JWT_SECRET_LEN:
            raise ValueError(f"JWT_SECRET must be at least {_MIN_JWT_SECRET_LEN} characters")
        return v

    @field_validator("app_timezone")
    @classmethod
    def _known_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown APP_TIMEZONE: {v}") from None
        return v

    @field_validator("groq_api_key")
    @classmethod
    def _non_empty_key(cls, v: SecretStr) -> SecretStr:
        if not v.get_secret_value().strip():
            raise ValueError("GROQ_API_KEY must not be empty")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
