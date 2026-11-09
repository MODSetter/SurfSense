"""Fetch-seam errors surfaced to the plugin's tools."""

from __future__ import annotations


class TikTokAccessBlockedError(RuntimeError):
    """Raised when every rotated IP is refused anonymous access.

    Distinguishes a hard block from an empty result; the tool reports it as its error.
    """
