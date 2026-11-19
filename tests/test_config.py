import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "qwen3:4b")
    assert Settings(_env_file=None).model == "qwen3:4b"
    monkeypatch.setenv("ROUTER_MODE", "decision")
    assert Settings(_env_file=None).model == "d3:2b"


def test_settings_reject_unknown_mode(monkeypatch):
    monkeypatch.setenv("ROUTER_MODE", "hybrid")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
