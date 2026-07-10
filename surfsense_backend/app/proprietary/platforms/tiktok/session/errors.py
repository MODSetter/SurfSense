"""Fetch-seam errors surfaced to the capability layer."""

from __future__ import annotations


class TikTokAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    Distinguishes a hard block from an empty result; the route maps it to 403.
    """
