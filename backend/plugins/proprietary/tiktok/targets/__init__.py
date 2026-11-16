"""TikTok URL classification into scrape targets."""

from __future__ import annotations

from .resolver import resolve_target
from .types import TargetKind, TikTokTarget

__all__ = ["TargetKind", "TikTokTarget", "resolve_target"]
