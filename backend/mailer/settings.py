"""The SMTP connection, under surfsense_backend's names and meanings, so a deployment copies its values."""

import os
from collections.abc import Mapping


class MailerSettings:
    def __init__(self, env: Mapping[str, str] = os.environ) -> None:
        # Off by default: a route that only mails answers 503 rather than claiming a send.
        self.SMTP_ENABLED = env.get("SMTP_ENABLED", "FALSE").strip().upper() == "TRUE"
        self.SMTP_HOST = env.get("SMTP_HOST", "").strip()
        self.SMTP_PORT = int(env.get("SMTP_PORT", "587"))
        self.SMTP_USERNAME = env.get("SMTP_USERNAME", "").strip()
        self.SMTP_PASSWORD = env.get("SMTP_PASSWORD", "")
        # Explicit, never guessed from the port: 465 is implicit TLS, 587 STARTTLS.
        self.SMTP_SECURITY = env.get("SMTP_SECURITY", "starttls").strip().lower()
        self.SMTP_TIMEOUT_SECONDS = int(env.get("SMTP_TIMEOUT_SECONDS", "20"))
        # The default sender; a feature may stamp its own on its messages.
        self.SMTP_FROM = env.get("SMTP_FROM", "").strip()


config = MailerSettings()
