"""Podcast generation: brief resolution, transcript drafting, and audio rendering.

The public surface grows as the module is built. For now it owns the
``podcasts`` table model, which :mod:`app.db` re-exports so existing
``from app.db import Podcast`` call sites keep working during the migration.
"""

from __future__ import annotations

__all__: list[str] = []
