"""End-to-end check against the running stack: `docker compose up -d && pytest -m e2e`."""

import os
import uuid

import httpx
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")
MAILHOG_URL = os.getenv("MAILHOG_URL", "http://localhost:8025")

pytestmark = pytest.mark.e2e


def captured_emails(reply_to: str) -> list[dict]:
    found = httpx.get(
        f"{MAILHOG_URL}/api/v2/search", params={"kind": "containing", "query": reply_to}
    )
    return [item["Content"]["Headers"] for item in found.raise_for_status().json()["items"]]


@pytest.mark.parametrize(
    ("message", "recipient"),
    [
        ("Nie działa mi komputer", "help-desk@example.com"),
        ("Chciałbym zgłosić urlop na jutro", "kadry@example.com"),
    ],
)
def test_message_reaches_the_right_department(message, recipient):
    sender = f"e2e-{uuid.uuid4().hex[:12]}@example.com"
    body = {"email": sender, "message": message}

    response = httpx.post(f"{API_URL}/api/v1/messages", json=body, timeout=180)

    assert response.status_code == 200, response.text
    assert response.json()["recipient"] == recipient

    emails = captured_emails(sender)
    assert len(emails) == 1
    assert emails[0]["To"] == [recipient]
    assert emails[0]["Reply-To"] == [sender]
