"""Mailer construction.

``SMTP_ENABLED`` is a deployment choice, not a fallback chain: an unreachable
or unconfigured mail server is an error to fix, never a reason to silently drop
mail. This mirrors the rule ``app/sandbox/factory.py`` states for sandbox
providers.

Off by default. Routes that exist only to mail something must refuse when mail
is disabled rather than reporting a send that never happened -- see
``is_mail_enabled``.
"""

from __future__ import annotations

import threading

from app.config import config

from .protocol import Mailer

_instance: Mailer | None = None
_instance_enabled: bool | None = None
_lock = threading.Lock()


def is_mail_enabled() -> bool:
    """Whether mail will actually be delivered.

    ``POST /license/resend`` always answers 200 so it cannot be used to probe
    which addresses are customers. A deployment that silently discards would
    therefore be indistinguishable from a working one, so the routes check this
    first and answer 503.
    """
    return config.SMTP_ENABLED


def build_mailer() -> Mailer:
    """Construct the SMTP sender. Raises if the connection is unconfigured."""
    from .smtp import SmtpMailer

    return SmtpMailer()


def get_mailer() -> Mailer:
    """Process-wide mailer, rebuilt if mail is toggled."""
    global _instance, _instance_enabled
    with _lock:
        if _instance is None or _instance_enabled != config.SMTP_ENABLED:
            _instance = build_mailer()
            _instance_enabled = config.SMTP_ENABLED
        return _instance


def reset_mailer() -> None:
    """Drop the cached instance. For tests that change configuration."""
    global _instance, _instance_enabled
    with _lock:
        _instance = None
        _instance_enabled = None
