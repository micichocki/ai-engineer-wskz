import smtplib

import pytest

from app.config import Settings
from app.departments import Department
from app.errors import MailDeliveryError
from app.mailer import build_email, send_email

SETTINGS = Settings(_env_file=None, smtp_host="127.0.0.1", smtp_port=1, smtp_timeout_seconds=1)


def test_build_email_sets_recipient_reply_to_and_original_body():
    email = build_email(
        sender="router@example.com",
        to=Department.KADRY,
        reply_to="jan.nowak@example.com",
        body="Chciałbym zgłosić urlop na jutro",
    )

    assert email["To"] == "kadry@example.com"
    assert email["Reply-To"] == "jan.nowak@example.com"
    assert email["From"] == "router@example.com"
    assert email.get_content().strip() == "Chciałbym zgłosić urlop na jutro"


def test_build_email_rejects_header_injection():
    with pytest.raises(ValueError):
        build_email(
            sender="router@example.com",
            to=Department.IT,
            reply_to="a@example.com\nBcc: evil@example.com",
            body="x",
        )


def test_send_email_hands_the_message_to_smtp(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.address = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send_message(self, email):
            sent.append(email)

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    send_email(SETTINGS, to=Department.HELP_DESK, reply_to="jan@example.com", body="hi")

    assert [m["To"] for m in sent] == ["help-desk@example.com"]


def test_quit_failure_after_delivery_is_not_a_delivery_error(monkeypatch):
    class FakeSMTP(smtplib.SMTP):
        def __init__(self, *args, **kwargs):
            pass

        def send_message(self, email):
            pass

        def __exit__(self, *exc):
            raise smtplib.SMTPResponseException(421, "bye")

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    send_email(SETTINGS, to=Department.IT, reply_to="jan@example.com", body="hi")


def test_send_email_reports_unreachable_server():
    with pytest.raises(MailDeliveryError, match=r"127\.0\.0\.1:1"):
        send_email(SETTINGS, to=Department.OTHER, reply_to="jan@example.com", body="hi")
