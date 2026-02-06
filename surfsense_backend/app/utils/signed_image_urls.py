"""
Access token utilities for generated images.

Provides token generation and verification so that generated images can be
served via <img> tags (which cannot pass auth headers) while still
restricting access to authorised users.

Each image generation record stores its own random access token.  The token
is verified by comparing the incoming query-parameter value against the
stored value in the database.  This approach:

* Survives SECRET_KEY rotation — tokens are random, not derived from a key.
* Allows explicit revocation — just clear the column.
* Is immune to timing attacks — uses ``hmac.compare_digest``.
"""

import hmac
import secrets


def generate_image_token() -> str:
    """
    Generate a cryptographically random access token for an image.

    Returns:
        A 64-character URL-safe hex string.
    """
    return secrets.token_hex(32)


def verify_image_token(stored_token: str | None, provided_token: str) -> bool:
    """
    Constant-time comparison of a stored token against a user-provided one.

    Args:
        stored_token: The token persisted on the ImageGeneration record.
        provided_token: The token from the URL query parameter.

    Returns:
        True if the tokens match, False otherwise.
    """
    if not stored_token or not provided_token:
        return False
    return hmac.compare_digest(stored_token, provided_token)
