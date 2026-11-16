"""End-to-end check against the running stack: `docker compose up -d && pytest -m e2e`.

Checks the pipeline (one e-mail, allowed recipient, Reply-To) on either variant. Whether the
department is the right one is measured by batch.py, and asserted here only with E2E_STRICT=1
(`make decision && E2E_STRICT=1 pytest -m e2e`).
"""

import os
import uuid

import httpx
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")
MAILHOG_URL = os.getenv("MAILHOG_URL", "http://localhost:8025")
STRICT = os.getenv("E2E_STRICT") == "1"

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
        ("Drukarka na drugim piętrze nie drukuje", "help-desk@example.com"),
        ("Zapomniałem hasła i nie mogę się zalogować do poczty", "help-desk@example.com"),
        ("VPN ciągle mi się rozłącza", "help-desk@example.com"),
        ("Chciałbym zgłosić urlop na jutro", "kadry@example.com"),
        ("Jestem na zwolnieniu lekarskim do piątku, gdzie wysłać L4?", "kadry@example.com"),
        ("Potrzebuję zaświadczenia o zatrudnieniu do banku", "kadry@example.com"),
        ("Nie dostałem wypłaty za październik", "kadry@example.com"),
        ("Proszę o założenie konta w systemie dla nowego pracownika", "it@example.com"),
        ("Potrzebuję dostępu do repozytorium projektu", "it@example.com"),
        ("Proszę o zakup licencji na PhpStorm", "it@example.com"),
        ("Potrzebujemy nowego serwera testowego dla zespołu", "it@example.com"),
        ("Chcę się zapisać na szkolenie z zarządzania projektami", "human-resources@example.com"),
        ("Mam konflikt z kolegą z zespołu i chcę to zgłosić", "human-resources@example.com"),
        ("Kiedy odbędzie się moja ocena okresowa?", "human-resources@example.com"),
        ("Chcę polecić znajomego na stanowisko programisty", "human-resources@example.com"),
        ("Jaka będzie jutro pogoda w Krakowie?", "other@example.com"),
        ("Kto wygrał wczorajszy mecz?", "other@example.com"),
        ("Gdzie mogę zaparkować rower pod biurem?", "other@example.com"),
        ("asdf qwerty", "other@example.com"),
    ],
)
def test_message_reaches_the_right_department(message, recipient):
    sender = f"e2e-{uuid.uuid4().hex[:12]}@example.com"
    body = {"email": sender, "message": message}

    response = httpx.post(f"{API_URL}/api/v1/messages", json=body, timeout=180)

    assert response.status_code == 200, response.text
    sent_to = response.json()["recipient"]
    assert sent_to == recipient if STRICT else sent_to.endswith("@example.com")

    emails = captured_emails(sender)
    assert len(emails) == 1
    assert emails[0]["To"] == [sent_to]
    assert emails[0]["Reply-To"] == [sender]
