"""send_email() — Gmail SMTP via App Password.

Wrapped behind one function so the provider can be swapped later (e.g. Resend)
without touching callers. Note: this package is named `emailer` (not `email`) so
it doesn't shadow Python's stdlib `email` module used below.
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER


def email_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASS)


def send_email(to: str, subject: str, html: str, text: str | None = None) -> None:
    """Send a multipart (text + HTML) email. Raises on misconfig / SMTP error."""
    if not email_configured():
        raise RuntimeError("SMTP not configured (SMTP_USER / SMTP_PASS missing).")
    if not to:
        raise RuntimeError("No recipient (ALERT_TO) provided.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(text or _html_to_text(html), "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Gmail App Passwords are shown with spaces ("xxxx xxxx xxxx xxxx"); strip them.
    password = SMTP_PASS.replace(" ", "")
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, password)
        server.sendmail(SMTP_USER, [to], msg.as_string())


def _html_to_text(html: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()
