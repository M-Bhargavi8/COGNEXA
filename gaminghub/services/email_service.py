"""
Outgoing email behind one function, send_email(), so the account flows
don't care how mail is delivered. The backend comes from MAIL_BACKEND:

* "smtp"     -- real delivery through any SMTP relay (stdlib smtplib, no
                extra dependency). Production uses this.
* "console"  -- writes the message to the application log. Development
                only: production config refuses it, since reset links
                would end up in log storage.
* "memory"   -- appends to app.extensions["mail_outbox"] (tests).
* "disabled" -- sends nothing and logs a warning.

Delivery failures are logged (without credentials) and reported as
False -- callers never surface SMTP errors to the visitor.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr

from flask import current_app

logger = logging.getLogger(__name__)


def get_outbox():
    return current_app.extensions.setdefault("mail_outbox", [])


def send_email(to, subject, body):
    config = current_app.config
    backend = config.get("MAIL_BACKEND", "console")

    message = EmailMessage()
    message["From"] = config.get("MAIL_DEFAULT_SENDER")
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    if backend == "memory":
        get_outbox().append({"to": to, "subject": subject, "body": body})
        return True

    if backend == "console":
        logger.info("Email (console backend, not delivered)\nTo: %s\nSubject: %s\n\n%s", to, subject, body)
        return True

    if backend == "disabled":
        logger.warning("Email not sent: MAIL_BACKEND is disabled (subject=%r).", subject)
        return False

    if backend != "smtp":
        logger.error("Email not sent: unknown MAIL_BACKEND %r.", backend)
        return False

    try:
        timeout = config.get("MAIL_TIMEOUT", 10)
        host, port = config["MAIL_SERVER"], config.get("MAIL_PORT", 587)

        if config.get("MAIL_USE_SSL"):
            server = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)

        with server:
            if config.get("MAIL_USE_TLS") and not config.get("MAIL_USE_SSL"):
                server.starttls(context=ssl.create_default_context())
            if config.get("MAIL_USERNAME"):
                server.login(config["MAIL_USERNAME"], config.get("MAIL_PASSWORD", ""))
            server.send_message(message)

        return True

    except (smtplib.SMTPException, OSError) as exc:
        # The exception text can include the server's reply but never
        # the password; the recipient's domain is enough to debug with.
        domain = parseaddr(to)[1].rpartition("@")[2]
        logger.error("Email delivery failed (subject=%r, domain=%s): %s", subject, domain, type(exc).__name__)
        return False
