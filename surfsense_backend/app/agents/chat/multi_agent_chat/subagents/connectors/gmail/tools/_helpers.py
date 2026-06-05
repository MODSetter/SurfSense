"""Shared helpers for Gmail connector tools.

Credential construction (``_build_credentials``) is also reused by the
Calendar connector tools, since both are Google OAuth backed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.db import SearchSourceConnector

_token_encryption_cache: object | None = None


def _get_token_encryption():
    global _token_encryption_cache
    if _token_encryption_cache is None:
        from app.config import config
        from app.utils.oauth_security import TokenEncryption

        if not config.SECRET_KEY:
            raise RuntimeError("SECRET_KEY not configured for token decryption.")
        _token_encryption_cache = TokenEncryption(config.SECRET_KEY)
    return _token_encryption_cache


def _build_credentials(connector: SearchSourceConnector):
    """Build Google OAuth Credentials from a connector's stored config.

    Handles both native OAuth connectors (with encrypted tokens) and
    Composio-backed connectors. Shared by Gmail and Calendar tools.
    """
    from app.utils.google_credentials import COMPOSIO_GOOGLE_CONNECTOR_TYPES

    if connector.connector_type in COMPOSIO_GOOGLE_CONNECTOR_TYPES:
        raise ValueError("Composio connectors must use Composio tool execution.")

    from google.oauth2.credentials import Credentials

    cfg = dict(connector.config)
    if cfg.get("_token_encrypted"):
        enc = _get_token_encryption()
        for key in ("token", "refresh_token", "client_secret"):
            if cfg.get(key):
                cfg[key] = enc.decrypt_token(cfg[key])

    exp = (cfg.get("expiry") or "").replace("Z", "")
    return Credentials(
        token=cfg.get("token"),
        refresh_token=cfg.get("refresh_token"),
        token_uri=cfg.get("token_uri"),
        client_id=cfg.get("client_id"),
        client_secret=cfg.get("client_secret"),
        scopes=cfg.get("scopes", []),
        expiry=datetime.fromisoformat(exp) if exp else None,
    )


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
