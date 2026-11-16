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
    assert Settings(_env_file=None).model == "qwen3:4b"
    monkeypatch.setenv("ROUTER_MODE", "decision")
    assert Settings(_env_file=None).model == "d3:2b"


def test_settings_reject_unknown_mode(monkeypatch):
    monkeypatch.setenv("ROUTER_MODE", "hybrid")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
