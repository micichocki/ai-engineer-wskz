from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "agent": the LLM picks the department and calls send_email.
    # "decision": the decision model picks it and code makes the same call.
    router_mode: Literal["agent", "decision"] = "agent"
    ollama_base_url: str = "http://ollama:11434"
    agent_model: str = "qwen3:1.7b"
    decision_model: str = "d3:2b"
    model_timeout_seconds: float = Field(default=120, gt=0)

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_timeout_seconds: float = Field(default=10, gt=0)
    mail_from: str = "message-router@example.com"

    @property
    def model(self) -> str:
        """The one model the selected mode uses."""
        return self.agent_model if self.router_mode == "agent" else self.decision_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
