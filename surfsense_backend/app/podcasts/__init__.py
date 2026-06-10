"""Podcast feature: brief resolution, transcript drafting, and audio rendering.

Owns the ``podcasts`` table model, which :mod:`app.db` re-exports so existing
``from app.db import Podcast`` imports keep resolving.
"""

from __future__ import annotations

__all__: list[str] = []
