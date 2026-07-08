"""Fetch-seam errors surfaced to the capability layer."""

from __future__ import annotations


class TikTokAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    Anonymous-only: we cannot log in, so a hard block is surfaced loudly rather
    than returning empty data. The route maps it to a 403.
    """
