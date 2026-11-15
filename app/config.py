from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://ollama:11434"
    agent_model: str = "qwen3:1.7b"
    decision_model: str = "d3:2b"
    # Below this confidence the agent is told to decide on its own.
    confidence_threshold: float = Field(default=0.8, ge=0, le=1)
    model_timeout_seconds: float = Field(default=120, gt=0)

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_timeout_seconds: float = Field(default=10, gt=0)
    mail_from: str = "message-router@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
