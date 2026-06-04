"""Backward-compatible shim.

The agent feature-flag resolver moved to :mod:`app.agents.shared.feature_flags`
as part of promoting the shared agent toolkit out of ``new_chat`` into the
cross-agent kernel. Import from there directly; this re-export keeps the
not-yet-retired single-agent stack working during the migration and will be
removed with it.
"""

from __future__ import annotations

from app.agents.shared.feature_flags import (
    AgentFeatureFlags,
    get_flags,
    reload_for_tests,
)

__all__ = [
    "AgentFeatureFlags",
    "get_flags",
    "reload_for_tests",
]
