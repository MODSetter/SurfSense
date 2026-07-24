"""Gmail-specific helpers for the Gmail connector tools.

Google OAuth credential construction lives in
``app.agents.chat.multi_agent_chat.subagents.connectors.google_auth`` (shared
with the Calendar connector). It is re-exported here under the legacy private
names so the existing Gmail tools keep importing it from this module.
"""

from __future__ import annotations

from typing import Any

from app.agents.chat.multi_agent_chat.subagents.connectors.google_auth import (
    build_credentials as _build_credentials,
    get_token_encryption as _get_token_encryption,
)

__all__ = [
    "_build_credentials",
    "_format_gmail_summary",
    "_get_token_encryption",
    "_gmail_headers",
]


def _gmail_headers(message: dict[str, Any]) -> dict[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    return {
        header.get("name", "").lower(): header.get("value", "")
        for header in headers
        if isinstance(header, dict)
    }


def _format_gmail_summary(message: dict[str, Any]) -> dict[str, Any]:
    headers = _gmail_headers(message)
    return {
        "message_id": message.get("id") or message.get("messageId"),
        "thread_id": message.get("threadId"),
        "subject": message.get("subject") or headers.get("subject", "No Subject"),
        "from": message.get("sender") or headers.get("from", "Unknown"),
        "to": message.get("to") or headers.get("to", ""),
        "date": message.get("messageTimestamp") or headers.get("date", ""),
        "snippet": message.get("snippet") or message.get("messageText", "")[:300],
        "labels": message.get("labelIds", []),
    }
