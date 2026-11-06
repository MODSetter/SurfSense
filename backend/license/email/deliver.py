"""Handing a built license email to the transport."""

from __future__ import annotations

import logging

from mailer import get_mailer, is_mail_enabled

from .address import normalize_email
from .message import BusinessCopy, LicenseEmailKind, build_license_email

logger = logging.getLogger(__name__)


async def deliver_licenses(
    kind: LicenseEmailKind,
    *,
    to: str,
    certificates: list[str] | tuple[str, ...],
    business: BusinessCopy | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Mail license files, if a provider is configured; whether the mailer took them.

    Silently doing nothing under the ``null`` transport is the failure mode
    this guards against elsewhere: routes check ``is_mail_enabled`` first and
    answer 503. This check is the backstop for non-route callers, and the
    answer lets one that records a send tell it from a skip.
    """
    if not certificates:
        return False
    if not is_mail_enabled():
        logger.warning(
            "Not sending %s license mail to %s: no mail transport configured", kind, to
        )
        return False

    message = build_license_email(
        kind,
        to=normalize_email(to),
        certificates=tuple(certificates),
        business=business,
        idempotency_key=idempotency_key,
    )
    await get_mailer().send(message)
    return True
