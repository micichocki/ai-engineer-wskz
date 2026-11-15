import pytest
from pydantic import ValidationError

from app.config import Settings
from app.departments import DESCRIPTIONS, Department


def test_addresses_match_the_task_list():
    assert {d.value for d in Department} == {
        "human-resources@example.com",
        "help-desk@example.com",
        "it@example.com",
        "kadry@example.com",
        "other@example.com",
    }


def test_every_department_has_a_description():
    assert set(DESCRIPTIONS) == set(Department)
    assert all(DESCRIPTIONS.values())


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "qwen3:4b")
    assert Settings(_env_file=None).agent_model == "qwen3:4b"


def test_settings_reject_invalid_threshold(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "1.5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
