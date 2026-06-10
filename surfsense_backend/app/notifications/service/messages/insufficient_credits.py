"""Pure presentation logic for insufficient-credit notifications."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.notifications.service.messages.text import truncate


def operation_id(document_name: str, search_space_id: int) -> str:
    """Build a unique id for an insufficient-credits notification."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    doc_hash = hashlib.md5(document_name.encode()).hexdigest()[:8]
    return f"insufficient_credits_{search_space_id}_{timestamp}_{doc_hash}"


def summary(
    document_name: str, balance_micros: int, required_micros: int
) -> tuple[str, str]:
    """Compute the title and message for a blocked-by-insufficient-credits document."""
    display_name = truncate(document_name, 40)
    title = f"Insufficient credits: {display_name}"
    balance_usd = max(0, balance_micros) / 1_000_000
    required_usd = max(0, required_micros) / 1_000_000
    message = (
        f"This document costs about ${required_usd:.2f} to process but you have "
        f"${balance_usd:.2f} of credit left. Add more credits to continue."
    )
    return title, message
