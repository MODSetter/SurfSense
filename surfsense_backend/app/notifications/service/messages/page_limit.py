"""Pure presentation logic for page-limit notifications."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.notifications.service.messages.text import truncate


def operation_id(document_name: str, search_space_id: int) -> str:
    """Build a unique id for a page-limit notification."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    doc_hash = hashlib.md5(document_name.encode()).hexdigest()[:8]
    return f"page_limit_{search_space_id}_{timestamp}_{doc_hash}"


def summary(
    document_name: str, pages_used: int, pages_limit: int, pages_to_add: int
) -> tuple[str, str]:
    """Compute the title and message for a blocked-by-page-limit document."""
    display_name = truncate(document_name, 40)
    title = f"Page limit exceeded: {display_name}"
    message = f"This document has ~{pages_to_add} page(s) but you've used {pages_used}/{pages_limit} pages. Upgrade to process more documents."
    return title, message
