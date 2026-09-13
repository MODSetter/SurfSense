"""Logs the envelope and writes attachments to a temp path. Local dev only."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from ..protocol import LicenseEmail

logger = logging.getLogger(__name__)


class ConsoleMailer:
    """Makes the whole flow developable end to end with no mail account."""

    async def send(self, message: LicenseEmail) -> None:
        outdir = Path(tempfile.gettempdir()) / "surfsense-mail"
        outdir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        for attachment in message.attachments:
            path = outdir / f"{message.kind}-{attachment.filename}"
            path.write_bytes(attachment.content)
            written.append(str(path))

        logger.info(
            "[console mailer] to=%s subject=%s\n%s\nattachments: %s",
            message.to,
            message.subject,
            message.text_body,
            ", ".join(written) or "none",
        )
