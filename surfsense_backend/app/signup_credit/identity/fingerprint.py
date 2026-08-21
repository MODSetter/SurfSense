"""One-way, keyed digest of an identity value."""

from __future__ import annotations

import hashlib
import hmac

from app.config import config


def fingerprint(value: str) -> str:
    """Digest an identity so it stays comparable but never readable."""
    # Keyed rather than a bare hash: the space of subject ids and email
    # addresses is small enough to exhaust offline.
    if not config.SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set before identities can be claimed.")

    return hmac.new(
        config.SECRET_KEY.encode(), value.encode(), hashlib.sha256
    ).hexdigest()
