"""Sends transactional email over SMTP (stdlib smtplib - no dependency).

Deliberately does not catch/swallow send failures: a misconfigured SMTP
server should be loudly observable somewhere (the caller decides how -
see services/accounts.py's request_password_reset, which logs a send
failure but still returns a generic success response for non-enumeration).
Silently pretending an email went out when it didn't would be exactly the
kind of unflagged failure CLAUDE.md's "never fabricate, say so explicitly"
principle argues against, even though that principle is written about club
data specifically.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_ADDRESS = os.environ.get("SMTP_FROM_ADDRESS", "")


def send_email(to: str, subject: str, body: str) -> None:
    """Raises on any SMTP/connection failure - see module docstring."""
    if not SMTP_HOST or not SMTP_FROM_ADDRESS:
        raise RuntimeError(
            "SMTP is not configured - set SMTP_HOST/SMTP_FROM_ADDRESS "
            "(and SMTP_USERNAME/SMTP_PASSWORD, if your provider needs auth) in .env."
        )

    msg = EmailMessage()
    msg["From"] = SMTP_FROM_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USERNAME:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)


def send_password_reset_email(to: str, reset_link: str) -> None:
    subject = "Reset your Cornell Club Matching Agent password"
    body = (
        "We got a request to reset your Cornell Club Matching Agent password.\n\n"
        f"Reset it here: {reset_link}\n\n"
        "This link expires in 1 hour and can only be used once. "
        "If you didn't request this, you can ignore this email."
    )
    send_email(to, subject, body)
