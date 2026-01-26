"""SMTP email sender — pure tool with no workflow state dependency."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from config.settings import settings

logger = logging.getLogger(__name__)


def send_email(
    to: str,
    body: str,
    message_id: str,
    subject: str = "Reply for availability",
) -> None:
    """
    Send a plain-text email via Gmail SMTP SSL.

    Args:
        to: Recipient address.
        body: Plain-text body.
        message_id: Message-ID of the original email (sets In-Reply-To header).
        subject: Subject line.

    Raises:
        ValueError: if body is None or empty.
        smtplib.SMTPException: on any SMTP failure.
    """
    if not body or not isinstance(body, str):
        raise ValueError(f"Invalid email body: {type(body).__name__} (expected str)")
    
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_USER_NAME
    msg["To"] = to
    msg["In-Reply-To"] = message_id

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as conn:
        conn.login(settings.EMAIL_USER_NAME, settings.EMAIL_PASSWORD)
        conn.send_message(msg)
    logger.info("Email sent to %s (reply to %s)", to, message_id)
