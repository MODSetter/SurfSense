"""Transport selection.

``LICENSE_MAIL_TRANSPORT`` picks *how* mail leaves the process -- discard, log,
or SMTP -- and never *who* delivers it. Every transactional provider exposes
SMTP, so changing vendor changes the SMTP connection strings and leaves this
setting on ``smtp``.

It is a deployment choice, not a fallback chain: an unreachable mail server is
an error to fix, never a reason to silently drop a license email. This mirrors
the rule ``app/sandbox/factory.py`` states for sandbox providers.
"""

from __future__ import annotations

import threading

from app.config import config

from .protocol import Mailer

_TRANSPORTS = ("null", "console", "smtp")

_instance: Mailer | None = None
_instance_transport: str | None = None
_lock = threading.Lock()


def is_mail_enabled() -> bool:
    """Whether the configured transport will actually deliver.

    Routes that exist only to mail something must refuse when this is false.
    A ``null`` provider returns success, and ``POST /license/resend`` always
    answers 200 so it cannot be used to probe emails -- together those would
    make a misconfigured deployment indistinguishable from a working one.
    """
    return config.LICENSE_MAIL_TRANSPORT in {"console", "smtp"}


def build_mailer() -> Mailer:
    """Construct the configured transport. Raises on an unknown name."""
    name = config.LICENSE_MAIL_TRANSPORT
    # Imported lazily so a deployment only pays for the transport it uses.
    if name == "null":
        from .transports.null import NullMailer

        return NullMailer()
    if name == "console":
        from .transports.console import ConsoleMailer

        return ConsoleMailer()
    if name == "smtp":
        from .transports.smtp import SmtpMailer

        return SmtpMailer()
    raise ValueError(
        f"Unknown LICENSE_MAIL_TRANSPORT {name!r}. Expected one of: "
        f"{', '.join(_TRANSPORTS)}"
    )


def get_mailer() -> Mailer:
    """Process-wide mailer, rebuilt if the configured transport changes."""
    global _instance, _instance_transport
    with _lock:
        if _instance is None or _instance_transport != config.LICENSE_MAIL_TRANSPORT:
            _instance = build_mailer()
            _instance_transport = config.LICENSE_MAIL_TRANSPORT
        return _instance


def reset_mailer() -> None:
    """Drop the cached instance. For tests that change configuration."""
    global _instance, _instance_transport
    with _lock:
        _instance = None
        _instance_transport = None
