"""The Stripe client, and the metadata of a checkout session as a plain dict."""

from __future__ import annotations

import logging
from typing import Any

from stripe import StripeClient

from license.settings import config

logger = logging.getLogger(__name__)


def get_stripe_client() -> StripeClient | None:
    """None when Stripe is unconfigured: an already fulfilled session is still served from Keygen."""
    if not config.STRIPE_SECRET_KEY:
        return None
    return StripeClient(config.STRIPE_SECRET_KEY)


def get_metadata(checkout_session: Any) -> dict[str, str]:
    """A ``StripeObject`` is no dict in stripe>=15; ``to_dict()`` is the supported way out."""
    metadata = getattr(checkout_session, "metadata", None)
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return {str(k): str(v) for k, v in metadata.items()}
    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        try:
            as_dict = to_dict(recursive=False)
            if isinstance(as_dict, dict):
                return {str(k): str(v) for k, v in as_dict.items()}
        except Exception:
            logger.exception(
                "Stripe metadata.to_dict() failed for session %s",
                getattr(checkout_session, "id", "?"),
            )
    inner = getattr(metadata, "_data", None)
    if isinstance(inner, dict):
        return {str(k): str(v) for k, v in inner.items()}
    logger.warning(
        "Could not extract metadata from checkout session %s (metadata type=%s)",
        getattr(checkout_session, "id", "?"),
        type(metadata).__name__,
    )
    return {}
