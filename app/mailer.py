import smtplib
from email.message import EmailMessage

from app.config import Settings
from app.departments import Department
from app.errors import MailDeliveryError


def build_email(*, sender: str, to: Department, reply_to: str, body: str) -> EmailMessage:
    """Forward the original message unchanged; replies go back to the requester."""
    email = EmailMessage()
    email["From"] = sender
    email["To"] = to.value
    email["Reply-To"] = reply_to
    email["Subject"] = f"New request from {reply_to}"
    email.set_content(body)
    return email


def connect(settings: Settings) -> smtplib.SMTP:
    return smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    )


def send_email(settings: Settings, *, to: Department, reply_to: str, body: str) -> None:
    email = build_email(sender=settings.mail_from, to=to, reply_to=reply_to, body=body)
    delivered = False
    try:
        with connect(settings) as smtp:
            smtp.send_message(email)
            delivered = True
    except (OSError, smtplib.SMTPException) as exc:
        if delivered:  # only QUIT failed; a 502 would invite a retry and a duplicate e-mail
            return
        raise MailDeliveryError(
            f"Could not deliver the e-mail via {settings.smtp_host}:{settings.smtp_port}: {exc}"
        ) from exc
