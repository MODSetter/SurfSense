"""Handing a built license email to the transport."""

from __future__ import annotations

import logging

from app.license.release import get_release_assets
from app.mailer import get_mailer, is_mail_enabled

from .address import normalize_email
from .message import LicenseEmailKind, build_license_email

logger = logging.getLogger(__name__)


async def deliver_licenses(
    kind: LicenseEmailKind,
    *,
    to: str,
    certificates: list[str] | tuple[str, ...],
    idempotency_key: str | None = None,
) -> None:
    """Mail license files, if a provider is configured.

    Silently doing nothing under the ``null`` transport is the failure mode
    this guards against elsewhere: routes check ``is_mail_enabled`` first and
    answer 503. This check is the backstop for non-route callers.
    """
    if not certificates:
        return
    if not is_mail_enabled():
        logger.warning(
            "Not sending %s license mail to %s: no mail transport configured", kind, to
        )
        return

    message = build_license_email(
        kind,
        to=normalize_email(to),
        certificates=tuple(certificates),
        idempotency_key=idempotency_key,
        installers=await get_release_assets(),
    )
    await get_mailer().send(message)
