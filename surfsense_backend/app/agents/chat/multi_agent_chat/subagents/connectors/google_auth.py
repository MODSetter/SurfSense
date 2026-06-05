"""Google OAuth credential construction shared across Google connectors.

Both the Gmail and Calendar connector tools are Google OAuth backed and build
``google.oauth2.credentials.Credentials`` from a stored ``SearchSourceConnector``
the same way. This module is the single owner of that logic so neither connector
has to import the other.
"""

from __future__ import annotations

from datetime import datetime

from app.db import SearchSourceConnector

_token_encryption_cache: object | None = None


def get_token_encryption():
    global _token_encryption_cache
    if _token_encryption_cache is None:
        from app.config import config
        from app.utils.oauth_security import TokenEncryption

        if not config.SECRET_KEY:
            raise RuntimeError("SECRET_KEY not configured for token decryption.")
        _token_encryption_cache = TokenEncryption(config.SECRET_KEY)
    return _token_encryption_cache


def build_credentials(connector: SearchSourceConnector):
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
        enc = get_token_encryption()
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
