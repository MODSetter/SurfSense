"""Discards every message. The default, and what unit tests use."""

from __future__ import annotations

import logging

from ..protocol import LicenseEmail

logger = logging.getLogger(__name__)


class NullMailer:
    """Accepts and drops.

    Routes must refuse to run under this transport rather than reporting
    success -- see ``factory.is_mail_enabled``.
    """

    async def send(self, message: LicenseEmail) -> None:
        logger.debug(
            "Mail discarded (transport=null): kind=%s to=%s", message.kind, message.to
        )
