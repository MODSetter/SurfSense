"""Backward-compatible shim.

Moved to ``app.agents.shared.middleware.permission``. Re-exported here for the
frozen single-agent stack (``chat_deepagent``/``subagents``).
"""

from app.agents.shared.middleware.permission import (
    PatternResolver,
    PermissionMiddleware,
    _normalize_permission_decision,
)

__all__ = [
    "PatternResolver",
    "PermissionMiddleware",
    "_normalize_permission_decision",
]
